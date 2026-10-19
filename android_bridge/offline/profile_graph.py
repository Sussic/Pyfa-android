"""Atomic C06 profiles + legacy declarative fit graph, isolated from packaged C04.

Envelope v9 retains the fit graph, characters, imports, targets and damage
patterns and detached implant sets in one GraphStore commit. Bound fit inputs are checked compatibility
projections of their named ledgers, never independent editable authority. Legacy files open without writes; the first edit
commits the envelope. Old bridges reject this format rather than lose profiles.
All EOS work reuses BridgeSession reconstruction and calculation, on its worker.
"""
from copy import deepcopy
import hashlib
import json
import re
import uuid

from android_bridge.contract import BridgeSession, _json
from .profile_store import GraphStore, StoredGraph, StoreError, StoreUncertain, StoreWriteRejected, decode_graph
from .profiles import Profiles, ProfileError, require
from .eos_profiles import materialize, edit_level
from . import target_profiles as targets
from . import damage_patterns as damage
from . import implant_sets


class MemoryStore(GraphStore):
    """Detached profile candidate only; durable commits belong to ProfileGraph."""
    def __init__(self, state=None):
        payload=_json(state) if state is not None else None
        self.current=StoredGraph(1,uuid.uuid4().hex,payload,hashlib.sha256(payload.encode()).hexdigest()) if payload else None
        self.opened_existing=state is not None
        self._durable=self.current

    def write(self, attempt): self._durable=attempt.after

    def confirm(self, attempt): return 'new' if self._durable==attempt.after else 'old'


class ProfileGraph:
    MAX_IMPORT_RECEIPTS = 128

    def __init__(self, engine, path, dataset, *, initial_spec=None, store_type=GraphStore):
        engine._check_thread()
        require(not engine._fits,'engine','Open on an empty exclusive EOS engine')
        from eos.saveddata.character import Character
        self.engine=engine
        self.dataset=dataset
        self.catalog=Character.getSkillIDMap()
        self._store=store_type(path)
        self._available=True
        self._bridge=BridgeSession(engine)
        self._bridge._dataset_identity=dataset
        self._state=None
        self._snapshots={}
        self.migration_pending=False
        try:
            if self._store.current:
                raw=decode_graph(self._store.current.payload)
                if raw.get('kind')=='pyfa.profile-fit-graph':
                    candidate=raw
                    self.migration_pending=raw.get('version')!=9
                else:
                    require(type(raw.get('records')) is dict and all(type(record) is dict and not {'implant_source','character_implants','character_security'} & record.keys() for record in raw['records'].values()), 'format', 'Character projections require a versioned profile envelope')
                    BridgeSession._validate_graph(raw,dataset,engine.settings)
                    candidate=self._from_legacy(raw)
                    self.migration_pending=True
                self._validate(candidate)
                candidate=self._migrate(candidate)
                snapshots=self._restore(candidate['fit_graph'], damage_ledger=candidate['damage_patterns'])
                self._state=candidate
                self._snapshots=snapshots
            else:
                graph=self._bridge._graph({}, {})
                if initial_spec is not None:
                    result=self._legacy_edit('create_fit',dict(spec=initial_spec))
                    require(result['status']=='ok','fit',str(result.get('error')))
                    graph=self._bridge._graph(self._bridge._records,self._bridge._revisions)
                candidate=self._from_legacy(graph)
                self._commit(candidate,set(graph['records']),advance=False)
        except Exception:
            self._available=False
            raise

    def _ready(self):
        self.engine._check_thread()
        require(self._available,'reopen_required','Reopen the profile fit graph')

    def _model(self, state=None):
        return Profiles('unused-memory-candidate',self.dataset,self.catalog,
                        store_type=lambda _:MemoryStore(state))

    def _from_legacy(self, graph):
        model=self._model()
        from eos.saveddata.character import Character
        names=Character.getSkillNameMap()
        for fit_id in graph['fit_order']:
            record=graph['records'][fit_id]
            # Distinct legacy fits remain independent even when names/skills match.
            # Legacy fit names permit whitespace/control characters that profile names reject.
            # Keep the original fit name unchanged; only normalize the generated label.
            label='Imported '+''.join(c if damage.unicodedata.category(c)!='Cc' and not 0xD800<=ord(c)<=0xDFFF else ' ' for c in record['spec']['name'])
            identity=model.create(label[:200].strip())['profile_id']
            draft=model.begin(identity)
            draft.values['default_level']=record['spec']['skill_level']
            overrides={}
            for name,value in record['skills'].items():
                require(name in names,'skill','Saved fit contains an unknown skill')
                overrides[str(names[name].ID)]=value
            draft.values['levels']=overrides
            model.save(draft)
            model.bind(fit_id,identity)
        return self._migrate(dict(kind='pyfa.profile-fit-graph',version=9,fit_graph=deepcopy(graph),profiles=model.snapshot(), imports={}, targets=targets.empty(), damage_patterns=damage.empty(), implant_sets=implant_sets.empty()))

    def _migrate(self, state):
        candidate=deepcopy(state)
        candidate.update(version=9, profiles=self._model(state['profiles']).snapshot())
        candidate.setdefault('imports', {})
        candidate.setdefault('targets', targets.empty())
        candidate['damage_patterns']=damage.normalized(candidate.get('damage_patterns', damage.empty()))
        candidate.setdefault('implant_sets', implant_sets.empty())
        for record in candidate['fit_graph']['records'].values():
            record.setdefault('implant_source', 'FIT')
        self._apply_profiles(candidate)
        return candidate

    def _projection(self, profile):
        character=materialize(profile)
        baseline=profile['default_level'] if profile['default_level'] is not None else 0
        levels={}
        for skill in character.skills:
            # EOS owns builtin side effects; no independently approximated rule.
            skill.level
            if skill.activeLevel!=baseline: levels[skill.item.name]=skill.activeLevel
        return baseline,levels

    def _apply_profiles(self, state):
        projected={}
        ledger=state['profiles']
        for fit_id,record in state['fit_graph']['records'].items():
            profile_id=ledger['bindings'][fit_id]['profile_id']
            if profile_id not in projected:
                projected[profile_id]=self._projection(ledger['profiles'][profile_id])
            baseline,levels=projected[profile_id]
            record['spec']['skill_level']=baseline
            record['skills']=deepcopy(levels)
            if state['version'] >= 5:
                from android_bridge.character_implants import display
                record['character_implants']=display(ledger['profiles'][profile_id]['implants'])
                record.setdefault('implant_source','FIT')
            if state['version'] >= 9:
                record['character_security']=ledger['profiles'][profile_id]['sec_status']
        targets.apply(state)
        damage.apply(state)

    def _validate(self, state, *, prospective=False):
        require(type(state) is dict and type(state.get('version')) is int
                and state['version'] in (1,2,3,4,5,6,7,8,9), 'format', 'Unsupported profile fit graph; data preserved')
        fields={'kind','version','fit_graph','profiles'} | ({'imports'} if state['version']>=2 else set()) | ({'targets'} if state['version']>=3 else set()) | ({'damage_patterns'} if state['version']>=4 else set()) | ({'implant_sets'} if state['version']>=6 else set())
        require(set(state)==fields and state['kind']=='pyfa.profile-fit-graph',
                'format','Unsupported profile fit graph; data preserved')
        if state['version']>=2:
            self._validate_imports(state['imports'],prospective=prospective)
        graph=state['fit_graph']
        require(type(graph) is dict and type(graph.get('records')) is dict, 'format', 'Invalid fit graph records')
        if state['version']>=3:
            targets.validate(state['targets'],graph['records'])
        if state['version']>=4:
            damage.validate(state['damage_patterns'],graph['records'],version=2 if state['version']>=7 else 1)
        if state['version']>=6:
            implant_sets.validate(state['implant_sets'])
        require(type(state['profiles']) is dict and type(state['profiles'].get('format')) is int and state['profiles']['format']==(3 if state['version']>=9 else 2 if state['version']>=5 else 1), 'format', 'Mixed profile ledger version')
        ledger=self._model(state['profiles']).snapshot()
        require(set(ledger['bindings'])==set(graph['records']),'reference','Profiles must bind exactly the surviving fits')
        for record in graph['records'].values():
            require(type(record) is dict, 'format', 'Invalid fit record')
            require(('implant_source' in record and 'character_implants' in record) if state['version']>=5 else ('implant_source' not in record and 'character_implants' not in record), 'format', 'Mixed character implant schema')
            require(('character_security' in record)==(state['version']>=9), 'format', 'Mixed character security schema')
        BridgeSession._validate_graph(graph,self.dataset,self.engine.settings,allow_named=state['version']>=8,
                                      allow_character_security=state['version']>=9)
        if state['version']>=9:
            from android_bridge.pilot_security import bound_profile
            for fit_id in graph['records']: bound_profile(state,fit_id)
        if state['version']>=8:
            from .named_rah import validate as validate_named
            validate_named(graph['records'],state['damage_patterns'],self.engine)
        from android_bridge.fitting import item
        if any(item(self.engine,identity).isAbyssal for identity in graph.get('recent',[])):
            raise StoreError('Saved recent use contains an unsupported item')
        projected=deepcopy(state)
        projected['profiles']=ledger
        self._apply_profiles(projected)
        for fit_id,record in graph['records'].items():
            expected=projected['fit_graph']['records'][fit_id]
            require(record['spec']['skill_level']==expected['spec']['skill_level'] and record['skills']==expected['skills'],
                    'profile_mismatch','Fit skill inputs disagree with the assigned profile')
            if state['version']>=5:
                require(damage.exact(record['character_implants'],expected['character_implants']), 'profile_mismatch', 'Character implant projection disagrees with assigned profile')
            if state['version']>=9:
                require(damage.exact(record['character_security'],expected['character_security']), 'profile_mismatch', 'Character security projection disagrees with assigned profile')

    def _restore(self, graph, *, damage_ledger):
        from .named_rah import Resolver
        bridge=self._bridge
        bridge._rah_resolver=Resolver(damage_ledger)
        bridge.sample_id=graph['sample_id']
        bridge._records={key:deepcopy(graph['records'][key]) for key in graph['fit_order']}
        bridge._revisions=deepcopy(graph['revisions'])
        bridge._modified=deepcopy(graph.get('modified',{key:0 for key in graph['fit_order']}))
        bridge._recent=deepcopy(graph.get('recent',[]))
        fits,snapshots=bridge._rebuild()
        captured=bridge._capture(fits,{key:row['spec'] for key,row in bridge._records.items()})
        for key,record in bridge._records.items():
            if 'inspection_ids' not in record:
                record['inspection_ids']=captured[key]['inspection_ids']
                graph['records'][key]['inspection_ids']=deepcopy(record['inspection_ids'])
        require(_json(captured)==_json(bridge._records),'replay','Fit inputs did not restore exactly')
        bridge._serialize_success('profile-rebuild',list(snapshots.values()))
        bridge._session.commit()
        bridge._fits=fits
        bridge._snapshots=snapshots
        bridge._provenance=dict(self.engine.resolved_item_ids)
        # This isolated envelope has no undo/redo API yet. Drop provisional bridge
        # history on replay rather than retaining entries for rolled-back edits.
        from android_bridge.history import EditHistory
        bridge._history=EditHistory()
        bridge._available=True
        return snapshots

    def snapshot(self):
        self._ready()
        return dict(graph=deepcopy(self._state),fits=deepcopy(self._snapshots),migration_pending=self.migration_pending)

    def _commit(self,candidate,named,*,advance=True,mark_named=True,before_write=None):
        self._ready()
        old=self._state
        old_provenance=dict(self.engine.resolved_item_ids) if hasattr(self.engine,'resolved_item_ids') else None
        if old is not None:
            from .graph_history import inputs
            same=targets.exact(inputs(old),inputs(candidate)) and all(
                targets.exact(old['fit_graph'].get(key),candidate['fit_graph'].get(key))
                for key in ('fit_order','recent','sample_id')) and targets.exact(old.get('imports',{}),candidate.get('imports',{}))
            if same:
                # A legacy operation may already have staged a detached replay.
                try:
                    if not damage.exact(self._bridge._records,old['fit_graph']['records']) or not damage.exact(self._bridge._revisions,old['fit_graph']['revisions']):
                        restored=self._restore(deepcopy(old['fit_graph']), damage_ledger=old.get('damage_patterns',damage.empty()))
                        require(_json(restored)==_json(self._snapshots),'recovery','No-op replay differs')
                    if old_provenance is not None:
                        self.engine.resolved_item_ids.clear();self.engine.resolved_item_ids.update(old_provenance)
                        self._bridge._provenance=old_provenance
                except Exception as error:
                    self._available=False
                    raise StoreUncertain('No-op replay failed; reopen the saved graph') from error
                if before_write is not None:before_write(old,self._snapshots,False)
                return dict(affected_fits=sorted(BridgeSession._affected(named,old['fit_graph']['records'],old['fit_graph']['records']) & old['fit_graph']['records'].keys()),snapshot=self.snapshot(),committed=False)
        candidate.update(version=9)
        candidate.setdefault('imports',{})
        candidate.setdefault('targets',targets.empty())
        candidate['damage_patterns']=damage.normalized(candidate.get('damage_patterns',damage.empty()))
        candidate.setdefault('implant_sets',implant_sets.empty())
        graph=candidate['fit_graph']
        old_records=old['fit_graph']['records'] if old else {}
        affected=BridgeSession._affected(named,old_records,graph['records']) & graph['records'].keys()
        if advance:
            previous=old['fit_graph']
            modified={key for key in graph['records'] if (mark_named and key in named) or
                      not targets.exact(graph['records'][key],old_records.get(key))}
            # Detached template/library commits do not consume a fit's ordering
            # counter, and an exhausted unrelated fit cannot block them.
            if modified:
                for value in previous.get('modified',{}).values():damage.integer(value,code='revision')
            sequence=damage.advance(max(previous.get('modified',{}).values(),default=0)) if modified else None
            graph['modified']={key:previous.get('modified',{}).get(key,0) for key in graph['records']}
            for key in graph['records']:
                current=previous['revisions'].get(key,0)
                if key in affected:
                    floor=getattr(self,'_revision_floor',{}).get(key,0)
                    damage.integer(current,code='revision');damage.integer(floor,code='revision')
                    graph['revisions'][key]=damage.advance(max(current,floor))
                else:graph['revisions'][key]=current
                if key in modified:graph['modified'][key]=sequence
        if self._store.current is not None:
            damage.advance(self._store.current.generation)
        confirmed=False
        # Ordinary bridge routes may have already staged a legacy edit before
        # entering this owner. Detached profile/set routes have not. A rejected
        # preflight must not reset live EOS merely in order to "recover" it.
        staged=old is not None and (not damage.exact(self._bridge._records,old_records) or
                                   not damage.exact(self._bridge._revisions,old['fit_graph']['revisions']))
        try:
            for revision in graph['revisions'].values():
                damage.integer(revision, 1, code='revision')
            self._validate(candidate,prospective=True)
            from android_bridge.projected_drone_budget import admit_transition
            admit_transition(old_records,graph['records'])
            staged=True
            snapshots=self._restore(graph, damage_ledger=candidate['damage_patterns'])
            # Fully serialize the proposed response before any durable write.
            _json(dict(graph=candidate,fits=snapshots,affected_fits=sorted(affected)))
            guard=getattr(self,'_feature_guard',None)
            if guard is not None:guard(candidate)
            if before_write is not None:before_write(candidate,snapshots,True)
            attempt=self._store.prepare(candidate)
            try: self._store.write(attempt)
            except Exception: pass
            try: outcome=self._store.confirm(attempt)
            except Exception as error: raise StoreUncertain('Cannot confirm profile/fit commit; reopen') from error
            if outcome!='new': raise StoreWriteRejected('Profile/fit edit not saved; previous graph is intact')
            confirmed=True
            self._store.accept(attempt)
            self._state=candidate
            self._snapshots=snapshots
            self.migration_pending=False
            return dict(affected_fits=sorted(affected),snapshot=self.snapshot(),committed=True)
        except Exception as error:
            if confirmed or isinstance(error,StoreUncertain):
                self._available=False
            elif old is not None and staged:
                try:
                    recovered=self._restore(deepcopy(old['fit_graph']), damage_ledger=old.get('damage_patterns',damage.empty()))
                    require(_json(recovered)==_json(self._snapshots),'recovery','Restored calculation differs')
                    if old_provenance is not None:
                        self.engine.resolved_item_ids.clear();self.engine.resolved_item_ids.update(old_provenance)
                        self._bridge._provenance=old_provenance
                except Exception:
                    self._available=False
                    raise StoreUncertain('Recovery failed; reopen the saved profile/fit graph') from error
            elif old_provenance is not None:
                self.engine.resolved_item_ids.clear();self.engine.resolved_item_ids.update(old_provenance)
                self._bridge._provenance=old_provenance
            raise

    def edit_target(self,operation,arguments,fit_id,*,profile_floor=None,binding_floor=None,before_write=None):
        self._ready()
        candidate=deepcopy(self._state)
        selected,named=targets.mutate(candidate,operation,arguments,fit_id,
            profile_floor=profile_floor,binding_floor=binding_floor)
        callback=None if before_write is None else lambda state,snapshots,changed:before_write(state,snapshots,changed,selected)
        result=self._commit(candidate,named,before_write=callback)
        result['target_id']=selected
        return result

    def damage_item_options(self,arguments,fit_id):
        self._ready()
        require(fit_id in self._state['fit_graph']['records'], 'missing_fit', 'Select an existing saved fit')
        damage.integer(arguments['fit_revision'], 1)
        require(arguments['fit_revision']==self._state['fit_graph']['revisions'][fit_id],
                'stale_fit', 'Saved fit changed; reload')
        return damage.item_options(self.engine,arguments['item_id'])

    def edit_damage(self,operation,arguments,fit_id,*,pattern_floor=None,binding_floor=None,before_write=None,before_stage=None):
        self._ready()
        candidate=deepcopy(self._state)
        item=self.damage_item_options(arguments,fit_id) if operation=='apply_item' else None
        if operation == 'set_module':
            from .named_rah import set_module
            selected,named=set_module(candidate,fit_id,arguments,self.engine)
        else:
            selected,named=damage.mutate(candidate,operation,arguments,fit_id,
                pattern_floor=pattern_floor,binding_floor=binding_floor,item=item)
        if before_stage is not None:
            from .graph_history import inputs
            if not damage.exact(inputs(self._state),inputs(candidate)):
                before_stage()
        callback=None if before_write is None else lambda state,snapshots,changed:before_write(state,snapshots,changed,selected,item)
        result=self._commit(candidate,named,before_write=callback)
        result['pattern_id']=selected
        return result

    def implant_set_catalogue(self):
        self._ready()
        if not hasattr(self, '_implant_set_catalogue'):
            self._implant_set_catalogue = implant_sets.predefined()
        return self._implant_set_catalogue

    def edit_implant_set(self,operation,arguments,fit_id,*,set_floor=None,before_write=None,before_stage=None):
        """Prepare one detached recipe or fit merge before any live EOS stage."""
        self._ready()
        candidate=deepcopy(self._state)
        ledger=candidate.setdefault('implant_sets',implant_sets.empty())
        catalogue=self.implant_set_catalogue()
        selected=None
        named=set()
        if operation in ('save_current','apply_fit'):
            require(fit_id in candidate['fit_graph']['records'],'missing_fit','Select an existing saved fit')
            damage.integer(arguments['fit_revision'],1)
            require(arguments['fit_revision']==candidate['fit_graph']['revisions'][fit_id],'stale_fit','Saved fit changed; reload')
        resolve_name=implant_sets.item_id_for_name
        if operation=='apply_fit':
            row=implant_sets.resolve(ledger,arguments['set_id'],catalogue,revision=arguments['revision'])
            require(not self._bridge._fits[fit_id].isStructure,'structure','Structures do not support implant sets')
            implant_sets.merge_fit(candidate['fit_graph']['records'][fit_id],row['item_ids'],resolve_name)
            selected=arguments['set_id']
            named={fit_id}
        else:
            current_ids=implant_sets.applied_ids(candidate,fit_id,resolve_name) if operation=='save_current' else None
            selected=implant_sets.mutate(ledger,operation,arguments,catalogue,revision_floor=set_floor,current_ids=current_ids)
        callback=None if before_write is None else lambda state,snapshots,changed:before_write(state,snapshots,changed,selected)
        from .graph_history import inputs
        if damage.exact(inputs(candidate),inputs(self._state)):
            # Unlike an ordinary legacy edit, this path has staged no live fit.
            # Keep no-ops entirely read-only, even at every exhausted counter.
            if callback is not None:callback(self._state,self._snapshots,False)
            return dict(affected_fits=[],snapshot=self.snapshot(),committed=False,set_id=selected)
        if before_stage is not None:before_stage()
        result=self._commit(candidate,named,before_write=callback)
        result['set_id']=selected
        return result

    def apply_implant_set_profile(self,set_id,revision,profile_id,profile_revision,*,before_write=None,before_stage=None):
        self._ready()
        row=implant_sets.resolve(self._state.get('implant_sets',implant_sets.empty()),set_id,
                                self.implant_set_catalogue(),revision=revision)
        # Validate editable target and strict revision even for an empty recipe.
        profile=self._model(self._state['profiles'])._profile(profile_id,editable=True)
        damage.integer(profile_revision,1)
        require(profile_revision==profile['revision'],'stale_profile','Character changed; reload')
        if not row['item_ids']:
            if before_write is not None:before_write(self._state,self._snapshots,False)
            return dict(affected_fits=[],snapshot=self.snapshot(),committed=False,profile_id=profile_id)
        return self._profile_change(lambda model:model.merge_implants(profile_id,profile_revision,row['item_ids']),
                                    before_write=before_write,before_stage=before_stage)

    def _profile_change(self,change,*,before_write=None,before_stage=None):
        self._ready()
        candidate=deepcopy(self._state)
        model=self._model(candidate['profiles'])
        result=change(model)
        candidate['profiles']=model.snapshot()
        if candidate['profiles']!=self._state['profiles']:
            if before_stage is not None:before_stage()
            damage.advance(self._store.current.generation)
            affected=BridgeSession._affected(set(result['affected_fits']),self._state['fit_graph']['records'],candidate['fit_graph']['records'])
            if affected:
                damage.advance(max(self._state['fit_graph'].get('modified',{}).values(),default=0))
            for key in affected:
                damage.advance(max(self._state['fit_graph']['revisions'][key],getattr(self,'_revision_floor',{}).get(key,0)))
        self._apply_profiles(candidate)
        committed=self._commit(candidate,set(result['affected_fits']),before_write=before_write)
        committed['profile_id']=result['profile_id']
        return committed

    def create_profile(self,name,*,source='builtin:all0',before_write=None):
        return self._profile_change(lambda model:model.create(name,source=source),before_write=before_write)

    def assign_profile(self,fit_id,profile_id,*,before_write=None):
        self._ready()
        require(fit_id in self._state['fit_graph']['records'],'missing_fit','Unknown fit')
        return self._profile_change(lambda model:model.bind(fit_id,profile_id),before_write=before_write)

    def set_profile_skill(self,profile_id,expected_revision,skill_id,value,*,before_write=None,before_stage=None):
        def change(model):
            draft=model.begin(profile_id)
            require(type(expected_revision) is int and draft.base_revision==expected_revision,
                    'conflict','Profile revision changed')
            draft.values['levels']=edit_level(draft.values,skill_id,value)
            return model.save(draft)
        return self._profile_change(change,before_write=before_write,before_stage=before_stage)

    def rename_profile(self,profile_id,expected_revision,name,*,before_write=None):
        def change(model):
            draft=model.begin(profile_id)
            require(type(expected_revision) is int and draft.base_revision==expected_revision,
                    'conflict','Profile revision changed')
            draft.values['name']=name
            return model.save(draft)
        return self._profile_change(change,before_write=before_write)

    def save_profile_security(self,profile_id,revision,sec_status,save_as,*,before_write=None,before_stage=None):
        return self._profile_change(lambda model:model.save_security(profile_id,revision,sec_status,save_as=save_as),
                                    before_write=before_write,before_stage=before_stage)

    def set_pilot_security(self,fit_id,fit_revision,pilot,*,before_write=None,before_stage=None):
        self._ready()
        require(type(fit_id) is str and fit_id in self._state['fit_graph']['records'],'missing_fit','Unknown fit')
        damage.integer(fit_revision,1,code='revision')
        require(fit_revision==self._state['fit_graph']['revisions'][fit_id],'conflict','Fit revision changed')
        from android_bridge.pilot_security import number, eligible, bound_profile, check_live
        number(pilot,nullable=True)
        self._model(self._state['profiles'])
        bound_profile(self._state,fit_id)
        record=self._state['fit_graph']['records'][fit_id]
        fit=self._bridge._fits[fit_id]
        check_live(record,fit)
        require(eligible(fit.ship.item),'unsupported_hull','This hull has no pilot security editor')
        old=record['spec']['security']['pilot']
        candidate=deepcopy(self._state)
        # Equality deliberately preserves same-source accepted raw encoding.
        # None versus numeric zero is a real source edit, including at zero.
        if (old is None)!=(pilot is None) or old!=pilot:
            if before_stage is not None:before_stage()
            candidate['fit_graph']['records'][fit_id]['spec']['security']['pilot']=pilot
        return self._commit(candidate,{fit_id},before_write=before_write)

    def delete_profile(self,profile_id,*,replacement=None,before_write=None):
        return self._profile_change(lambda model:model.delete(profile_id,replacement=replacement),before_write=before_write)

    def add_profile_implant(self,profile_id,revision,item_id,replace_implant_id,*,before_write=None):
        return self._profile_change(lambda model:model.add_implant(profile_id,revision,item_id,replace_implant_id),before_write=before_write)

    def remove_profile_implant(self,profile_id,revision,implant_id,*,before_write=None):
        return self._profile_change(lambda model:model.remove_implant(profile_id,revision,implant_id),before_write=before_write)

    def set_implant_source(self,fit_id,fit_revision,source,*,before_write=None):
        self._ready()
        require(type(fit_id) is str and fit_id in self._state['fit_graph']['records'],'missing_fit','Unknown fit')
        damage.integer(fit_revision,1,code='revision')
        require(fit_revision==self._state['fit_graph']['revisions'][fit_id],'conflict','Fit revision changed')
        require(type(source) is str and source in ('FIT','CHARACTER'),'source','Invalid implant source')
        require(not self._bridge._fits[fit_id].isStructure,'structure','Structures do not support implant source selection')
        candidate=deepcopy(self._state)
        candidate['fit_graph']['records'][fit_id]['implant_source']=source
        return self._commit(candidate,{fit_id},before_write=before_write)

    def _legacy_edit(self,operation,arguments):
        bridge=self._bridge
        ids={arguments[k] for k in ('fit_id','source_id','target_id') if k in arguments}
        request=dict(version=1,request_id=uuid.uuid4().hex,session_id=bridge.session_id,
            operation=operation,expected_revisions={k:bridge._revisions[k] for k in ids},arguments=arguments)
        return json.loads(bridge.dispatch(_json(request)))

    def edit_fit(self,operation,arguments):
        """Reuse normal fit edits, but prohibit bypassing shared profile authority."""
        self._ready()
        require(operation not in ('set_skill_level','undo','redo','snapshot'),
                'operation','Use profile skill edits; history integration is pending')
        old=deepcopy(self._state)
        try:
            result=self._legacy_edit(operation,arguments)
            if result['status']!='ok':
                # Valid but unfittable items still enter recent use in the legacy
                # bridge. Save that metadata atomically, while retaining rejection.
                recent=deepcopy(self._bridge._recent)
                if recent!=old['fit_graph'].get('recent',[]):
                    candidate=deepcopy(old)
                    candidate['fit_graph']['recent']=recent
                    self._commit(candidate,set(),advance=False)
                raise ProfileError('fit',str(result.get('error')))
            graph=self._bridge._graph(deepcopy(self._bridge._records),deepcopy(self._bridge._revisions))
            model=self._model(old['profiles'])
            for fit_id in set(old['fit_graph']['records'])-set(graph['records']): model.unbind(fit_id)
            new=set(graph['records'])-set(old['fit_graph']['records'])
            for fit_id in new:
                if operation=='duplicate_fit':
                    model.bind(fit_id,old['profiles']['bindings'][arguments['fit_id']]['profile_id'])
                else:
                    migrated=self._from_legacy(dict(graph,fit_order=[fit_id],records={fit_id:graph['records'][fit_id]}))
                    profile_id=migrated['profiles']['bindings'][fit_id]['profile_id']
                    state=model.snapshot()
                    state['profiles'][profile_id]=migrated['profiles']['profiles'][profile_id]
                    state['bindings'][fit_id]=migrated['profiles']['bindings'][fit_id]
                    model=self._model(state)
            candidate=deepcopy(old)
            candidate.update(fit_graph=graph,profiles=model.snapshot())
            ledger=candidate.setdefault('targets',targets.empty())
            for key in set(ledger['bindings'])-set(graph['records']):
                del ledger['bindings'][key]
            if operation=='duplicate_fit':
                source=old.get('targets',targets.empty())['bindings'].get(arguments['fit_id'])
                if source is not None:
                    for key in new:ledger['bindings'][key]=dict(target_id=source['target_id'],revision=1)
            elif operation=='set_target_profile':
                ledger['bindings'].pop(arguments['fit_id'],None)
            damage_ledger=candidate['damage_patterns']=damage.normalized(candidate.get('damage_patterns',damage.empty()))
            candidate.setdefault('implant_sets',implant_sets.empty())
            for key in set(damage_ledger['bindings'])-set(graph['records']):
                del damage_ledger['bindings'][key]
            if operation=='duplicate_fit':
                source=old.get('damage_patterns',damage.empty())['bindings'].get(arguments['fit_id'])
                if source is not None:
                    for key in new:damage_ledger['bindings'][key]=dict(pattern_id=source['pattern_id'],revision=1)
            elif operation=='set_damage_pattern':
                if damage_ledger['bindings'].pop(arguments['fit_id'],None) is not None:
                    # The legacy bridge validates the request, but its anonymous
                    # magnitude-equality guard may preserve old numeric kinds.
                    # A named inline save explicitly chooses these submitted raw
                    # values; replay this detached candidate through the normal
                    # owner before committing instead of retaining that shortcut.
                    graph['records'][arguments['fit_id']]['spec']['damage_pattern']=deepcopy(arguments['pattern'])
            self._apply_profiles(candidate)
            named=(new if operation in ('create_fit','duplicate_fit') else
                   {arguments[k] for k in ('fit_id','source_id','target_id') if k in arguments})
            return self._commit(candidate,named,mark_named=False)
        except Exception:
            if self._available:
                try: self._restore(deepcopy(self._state['fit_graph']), damage_ledger=self._state.get('damage_patterns',damage.empty()))
                except Exception: self._available=False
            raise

    @staticmethod
    def _import_key(request_id,fingerprint):
        require(type(request_id) is str and re.fullmatch('[A-Za-z0-9_-]{1,128}',request_id),
                'request','Invalid import request identity')
        require(type(fingerprint) is str and re.fullmatch('[0-9a-f]{64}',fingerprint),
                'request','Invalid import request fingerprint')

    def _validate_imports(self,imports,*,prospective=False):
        require(type(imports) is dict and len(imports)<=self.MAX_IMPORT_RECEIPTS,
                'format','Invalid import receipt ledger')
        seen_ids=set()
        seen_generations=set()
        for request_id,receipt in imports.items():
            require(type(receipt) is dict and set(receipt)=={'fingerprint','fit_ids','names','fit_revisions','generation'},
                    'format','Invalid import receipt')
            self._import_key(request_id,receipt['fingerprint'])
            ids,names=receipt['fit_ids'],receipt['names']
            require(type(ids) is list and 1<=len(ids)<=16 and
                    all(type(i) is str and re.fullmatch('[0-9a-f]{32}',i) for i in ids) and
                    len(ids)==len(set(ids)), 'format','Invalid imported fit identities')
            require(not seen_ids.intersection(ids),'format','Imported fit identity was reused')
            seen_ids.update(ids)
            require(type(names) is list and len(names)==len(ids) and
                    all(type(n) is str and 0<len(n)<=1024 for n in names),
                    'format','Invalid imported fit names')
            require(type(receipt['fit_revisions']) is list and
                    len(receipt['fit_revisions'])==len(ids) and
                    all(type(r) is int and r==1 for r in receipt['fit_revisions']),
                    'format','Invalid imported fit revisions')
            require(type(receipt['generation']) is int and 1<=receipt['generation']<2**63,
                    'format','Invalid import commit generation')
            require(receipt['generation'] not in seen_generations,'format','Duplicate import commit generation')
            seen_generations.add(receipt['generation'])
            limit=self._store.current.generation+(1 if prospective else 0)
            require(receipt['generation']<=limit,'format','Import receipt is newer than its saved graph')

    def _verify_durable(self):
        try:
            fresh=self._store._read()
        except Exception as error:
            self._available=False
            raise StoreUncertain('Cannot verify saved graph freshness; reopen') from error
        if fresh!=self._store.current:
            self._available=False
            raise StoreUncertain('Saved graph changed in another session; reopen')

    def import_receipt(self,request_id,fingerprint):
        """Read-only replay check, deliberately before stale profile/graph checks.

        Returned IDs describe the original commit; later deleted fits are never
        recreated and later edits do not change the historical receipt.
        """
        self._ready()
        self._import_key(request_id,fingerprint)
        receipt=self._state.get('imports',{}).get(request_id)
        if receipt is not None:
            require(receipt['fingerprint']==fingerprint,'request_conflict',
                    'Import request identity was already used for different inputs')
            self._verify_durable()
            return deepcopy(receipt)
        return None

    def import_context(self,profile_id):
        self._ready()
        profile=self._model(self._state['profiles'])._profile(profile_id)
        return dict(dataset=self.dataset,graph=dict(generation=self._store.current.generation,
                    token=self._store.current.token),profile=dict(id=profile_id,revision=profile['revision']))

    def import_specs(self,specs,*,request_id,fingerprint,expected_generation,
                     expected_token,profile_id,expected_profile_revision):
        """Trusted adapter batch boundary; no public edit_fit loop or partial saves.

        The adapter fingerprints and validates original source documents; this
        method validates every generated spec through the existing bridge/EOS.
        Provisional fits stay in the exclusive in-memory engine until one commit.
        """
        self._ready()
        receipt=self.import_receipt(request_id,fingerprint)
        if receipt is not None:
            return dict(receipt=receipt,replayed=True)
        require(type(expected_generation) is int and type(expected_token) is str and
                self._store.current.generation==expected_generation and
                self._store.current.token==expected_token,
                'stale_graph','The fit graph changed; refresh the import preview')
        self._verify_durable()
        model=self._model(self._state['profiles'])
        profile=model._profile(profile_id)
        require(type(expected_profile_revision) is int and
                expected_profile_revision==profile['revision'],
                'stale_profile','The skill profile changed; refresh the import preview')
        require(len(self._state.get('imports',{}))<self.MAX_IMPORT_RECEIPTS,
                'receipt_capacity','Import receipt capacity reached; no import was saved')
        require(type(specs) is list and 1<=len(specs)<=16,'request','Supply 1 to 16 fit specs')
        require(self._bridge._store is None,'engine_error','Batch staging requires a detached bridge')
        # Reserve the complete import before the first provisional create, so
        # even a rejected later document cannot repeatedly evaluate an unsafe
        # projected-drone graph. Existing legacy-only acceptance is unchanged.
        from android_bridge.projected_drone_budget import admit, present
        from android_bridge.projected_drone_admission import AdmissionRejected
        if present(self._bridge._records) or any(type(s) is dict and (s.get('projected_drones') or s.get('projected_fighters')) for s in specs):
            from android_bridge.contract import _spec, ContractError
            prospective=deepcopy(self._bridge._records)
            try:
                for index,spec in enumerate(specs):
                    _spec(spec)
                    prospective['import-reservation-'+str(index)]=dict(
                        spec=deepcopy(spec), skills={}, implants=[], boosters=[], projections=[], commands=[],
                        implant_source='FIT', character_implants=__import__('android_bridge.character_implants',fromlist=['display']).display(profile['implants']))
                admit(prospective, request_phases=max(8, 2*len(specs)+3))
            except AdmissionRejected as error:
                raise ProfileError('evaluation_budget', str(error)) from error
            except ContractError as error:
                raise ProfileError('invalid_fitting', str(error)) from error
        from android_bridge.projected_drone_cap_budget import import_scope
        with import_scope(self.engine, len(specs)):
            # Validate the old recoverable graph at the elevated batch factor
            # before any staging. A refusal here changes derived caches only;
            # normal reads retain the ordinary factor after scope exit.
            if present(self._bridge._records):
                for fit in self._bridge._fits.values():
                    self.engine.prepare_read(fit)
            return self._stage_import_specs(specs, request_id, fingerprint, profile_id, model)

    def _stage_import_specs(self, specs, request_id, fingerprint, profile_id, model):
        old=deepcopy(self._state)
        ids=[]
        rejected=[]
        try:
            for index,spec in enumerate(specs):
                previous=set(self._bridge._records)
                result=self._legacy_edit('create_fit',dict(spec=deepcopy(spec)))
                if result['status']!='ok':
                    code=result.get('error',{}).get('code')
                    message=result.get('error',{}).get('message','')
                    if code=='INVALID_EDIT' and type(message) is str and message.startswith((
                            'Projected-drone evaluation budget:', 'Projected-drone capacitor evaluation budget:')):
                        raise ProfileError('evaluation_budget',
                            'Projected-drone evaluation budget: import exceeds the reviewed request reservation; no fits were saved')
                    if code not in ('INVALID_EDIT','INVALID_REQUEST'):
                        raise ProfileError('engine_error','The fitting engine could not prepare the import')
                    rejected.append(index)
                    continue
                created=set(self._bridge._records)-previous
                require(len(created)==1,'replay','Import did not create exactly one fitting')
                identity=created.pop()
                if any('empty_slot' in row for row in spec.get('modules',[])):
                    fit=self._bridge._fits[identity]
                    from android_bridge.fitting import VACANT_SLOTS
                    if any(sum(m.slot==slot for m in fit.modules)>fit.getNumSlots(slot)
                           for slot in VACANT_SLOTS.values()):
                        rejected.append(index)
                        continue
                ids.append(identity)
                model.bind(identity,profile_id)
            if rejected:
                error=ProfileError('invalid_fitting','Imported fittings contain incompatible equipment or inputs')
                error.documents=rejected
                raise error
            graph=self._bridge._graph(deepcopy(self._bridge._records),deepcopy(self._bridge._revisions))
            candidate=deepcopy(old)
            candidate.update(version=max(2,candidate['version']),fit_graph=graph,profiles=model.snapshot())
            candidate.setdefault('imports',{})
            receipt=dict(fingerprint=fingerprint,fit_ids=ids,
                         names=[graph['records'][key]['spec']['name'] for key in ids],
                         fit_revisions=[1 for key in ids],generation=self._store.current.generation+1)
            candidate['imports'][request_id]=receipt
            self._apply_profiles(candidate)
            self._commit(candidate,set(ids),mark_named=False)
            return dict(receipt=deepcopy(receipt),replayed=False)
        except Exception:
            if self._available:
                try:
                    restored=self._restore(deepcopy(self._state['fit_graph']), damage_ledger=self._state.get('damage_patterns',damage.empty()))
                    require(_json(restored)==_json(self._snapshots),'recovery','Imported fit rollback differs')
                except Exception as error:
                    self._available=False
                    raise StoreUncertain('Import recovery failed; reopen the saved graph') from error
            raise
