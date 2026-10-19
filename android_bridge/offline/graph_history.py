"""Session-local atomic actions over fit inputs and shared profile authority.

Receipts, revisions, recent use and modification order are never rolled back.
A shared action can be reversed only while it is the current action for every
participant. Field-level conflict checks preserve unrelated direct note writes.
"""
from copy import deepcopy
from dataclasses import dataclass
from android_bridge.history import Change, LIMIT
from .target_profiles import empty, exact as _same
from . import damage_patterns as damage
from . import implant_sets


def _changes(before,after,path=()):
    """Shared authority includes raw named-input kinds and signed-zero identity."""
    for key in sorted(before.keys() | after.keys()):
        a,b=before.get(key),after.get(key)
        if key in before and key in after and type(a) is dict and type(b) is dict:
            yield from _changes(a,b,(*path,key))
        elif key not in before or key not in after or not _same(a,b):
            yield Change((*path,key),key in before,deepcopy(a),key in after,deepcopy(b))


def inputs(state):
    profiles=deepcopy(state['profiles'])
    for record in profiles['profiles'].values():record.pop('revision',None)
    for binding in profiles['bindings'].values():binding.pop('revision',None)
    targets=deepcopy(state.get('targets',empty()))
    for record in targets['profiles'].values():record.pop('revision',None)
    for binding in targets['bindings'].values():binding.pop('revision',None)
    # Schema migration is normalization, never an undoable user change.
    patterns=damage.normalized(state.get('damage_patterns',damage.empty()))
    for record in patterns['patterns'].values():record.pop('revision',None)
    for binding in patterns['bindings'].values():binding.pop('revision',None)
    sets=deepcopy(state.get('implant_sets',implant_sets.empty()))
    for record in sets['sets'].values():record.pop('revision',None)
    records=deepcopy(state['fit_graph']['records'])
    for fit_id,record in records.items():
        record.pop('skills',None)
        record.pop('character_implants',None)
        record.pop('character_security',None)
        record.get('spec',{}).pop('skill_level',None)
        if fit_id in targets['bindings']:record.get('spec',{}).pop('target_profile',None)
        if fit_id in patterns['bindings']:record.get('spec',{}).pop('damage_pattern',None)
    return dict(records=records,profiles=profiles,targets=targets,damage_patterns=patterns,implant_sets=sets)


@dataclass(frozen=True)
class Action:
    sequence: int
    label: str
    participants: frozenset
    changes: tuple
    recent: tuple
    legacy_token: object = None
    created_order: tuple = ()
    damage_holders: tuple = ()


class GraphHistory:
    def __init__(self, rows=None, sequence=0):
        self.rows={} if rows is None else rows
        self.sequence=sequence

    def details(self, fit_id):
        actions,cursor=self.rows.get(fit_id,((),0))
        return dict(undo_count=cursor,redo_count=len(actions)-cursor,limit=LIMIT,
                    undo_label=actions[cursor-1].label if cursor else None,
                    redo_label=actions[cursor].label if cursor<len(actions) else None)

    def _drop(self, removed):
        rows={}
        for key,(actions,cursor) in self.rows.items():
            rows[key]=(tuple(a for a in actions if id(a) not in removed),
                       sum(id(a) not in removed for a in actions[:cursor]))
        return GraphHistory(rows,self.sequence)

    def _append(self,action):
        # Branching and eviction invalidate the same shared action everywhere.
        removed=set()
        for key in action.participants:
            actions,cursor=self.rows.get(key,((),0))
            removed.update(id(a) for a in actions[cursor:])
            removed.update(id(a) for a in actions[:max(0,cursor+1-LIMIT)])
        rows=self._drop(removed).rows
        for key in action.participants:
            actions,cursor=rows.get(key,((),0))
            rows[key]=(*actions,action),cursor+1
        return GraphHistory(rows,action.sequence)

    def record(self,before,after,label,participants,recent=()):
        changes=tuple(_changes(inputs(before),inputs(after)))
        if not changes or not participants:return self
        created=tuple(key for key in after['fit_graph'].get('fit_order',after['fit_graph']['records'])
                      if key not in before['fit_graph']['records'])
        from .profiles import advance
        from .named_rah import inventory
        old, new = before.get('damage_patterns', damage.empty()), after.get('damage_patterns', damage.empty())
        meaning = lambda row: None if row is None else {key: value for key, value in row.items() if key != 'revision'}
        changed = sorted(key for key in old['patterns'].keys() | new['patterns'].keys()
                         if not damage.exact(meaning(old['patterns'].get(key)), meaning(new['patterns'].get(key))))
        holders = tuple((key, inventory(before['fit_graph']['records'], old, key),
                        inventory(after['fit_graph']['records'], new, key)) for key in changed)
        return self._append(Action(advance(self.sequence),label,frozenset(participants),changes,tuple(recent),
                                   created_order=created,damage_holders=holders))

    def record_legacy(self,label,fit_id,token):
        from .profiles import advance
        return self._append(Action(advance(self.sequence),label,frozenset((fit_id,)),(),(),token))

    def sync_legacy(self,history):
        rows={}
        for key,(actions,cursor) in self.rows.items():
            valid={id(a) for a in history.rows.get(key,((),0))[0]}
            keep=[a for a in actions if a.legacy_token is None or id(a.legacy_token) in valid]
            new_cursor=sum(a in keep for a in actions[:cursor])
            rows[key]=(tuple(keep),new_cursor)
        return GraphHistory(rows,self.sequence)

    def prune(self,live_ids):
        removed={id(a) for actions,cursor in self.rows.values() for a in actions
                 if not a.participants<=live_ids}
        kept=self._drop(removed)
        return GraphHistory({k:v for k,v in kept.rows.items() if k in live_ids},self.sequence)

    def replay(self,fit_id,redo,state):
        actions,cursor=self.rows.get(fit_id,((),0))
        if redo and cursor==len(actions) or not redo and cursor==0:
            raise ValueError('No redo action available' if redo else 'No undo action available')
        action=actions[cursor if redo else cursor-1]
        for key in action.participants:
            others,position=self.rows.get(key,((),0))
            index=position if redo else position-1
            if index<0 or index>=len(others) or others[index] is not action:
                raise ValueError('Undo newer edits on every affected fit first')
        from .named_rah import inventory
        from .profiles import require
        for key, before_holders, after_holders in action.damage_holders:
            expected = before_holders if redo else after_holders
            require(damage.exact(inventory(state['fit_graph']['records'], state['damage_patterns'], key), expected),
                    'history_dependency', 'Undo later module or incoming damage assignments before this shared action')
        result=inputs(state)
        for change in action.changes:
            parent=result
            for name in change.path[:-1]:
                if name not in parent:raise ValueError('History inputs no longer exist')
                parent=parent[name]
            key=change.path[-1]
            present,value=(change.before_present,change.before) if redo else (change.after_present,change.after)
            if (key in parent)!=present or present and not _same(parent[key],value):
                raise ValueError('Inputs changed outside this action; history was preserved')
            present,value=(change.after_present,change.after) if redo else (change.before_present,change.before)
            if present:parent[key]=deepcopy(value)
            else:parent.pop(key,None)
        for key, before_holders, after_holders in action.damage_holders:
            expected = after_holders if redo else before_holders
            require(damage.exact(inventory(result['records'], result['damage_patterns'], key), expected),
                    'history_dependency', 'Replayed damage holder identities differ; history was preserved')
        rows=dict(self.rows)
        for key in action.participants:
            values,position=rows[key];rows[key]=(values,position+(1 if redo else -1))
        return result,GraphHistory(rows,self.sequence),action
