"""Current Android bridge facade: one atomic graph authority, existing fit wire.

Read APIs retain the original BridgeSession implementation. The original
per-fit EditHistory still owns ordinary fitting reversal; a shared timeline
adds profile/import actions without replacing its field-level replay rules.
"""
from copy import deepcopy
import json
from android_bridge.contract import BridgeSession, ContractError, _json, _pairs
from android_bridge.history import LABELS, LIMIT, _same
from .profile_graph import ProfileGraph
from .profiles import ProfileError, require, advance
from .profile_store import StoreUncertain, StoreWriteRejected
from .graph_history import GraphHistory, inputs
from . import target_profiles as targets
from . import damage_patterns as damage
from . import implant_sets


class IntegratedGraph(ProfileGraph):
    def __init__(self,*args,**kwargs):
        self._revision_floor={}
        super().__init__(*args,**kwargs)

    def _restore(self,graph,*,damage_ledger):
        history=self._bridge._history
        result=super()._restore(graph,damage_ledger=damage_ledger)
        self._bridge._history=history
        return result

    def _commit(self,candidate,named,**kwargs):
        try:
            result=super()._commit(candidate,named,**kwargs)
        finally:
            if not self._available:self._bridge._available=False
        try:
            for key,value in self._state['fit_graph']['revisions'].items():
                self._revision_floor[key]=max(value,self._revision_floor.get(key,0))
        except Exception:
            self._available=False
            self._bridge._available=False
            raise
        return result


class NativeSession:
    def __init__(self,engine,path,dataset,spec):
        self.graph=IntegratedGraph(engine,path,dataset,initial_spec=spec)
        self.history=GraphHistory()
        self._pending_history=False
        self._profile_floor={}
        self._binding_floor={}
        self._target_profile_floor={}
        self._target_binding_floor={}
        self._damage_pattern_floor={}
        self._damage_binding_floor={}
        self._implant_set_floor={}
        self._remember_versions()
        self.graph._feature_guard=self._guard_feature_publication

    def __getattr__(self,name):
        if name in {'_fits','_records','_revisions','_snapshots','_specs'}:self.graph._ready()
        value=getattr(self.graph._bridge,name)
        if callable(value) and not name.startswith('_'):
            def guarded(*args,**kwargs):
                self.graph._ready()
                return value(*args,**kwargs)
            return guarded
        return value

    def _disable(self):
        self.graph._available=False
        self.graph._bridge._available=False

    @property
    def _store(self):return self.graph._store

    @property
    def _available(self):return self.graph._available and self.graph._bridge._available

    @property
    def persistence_info(self):
        store=self._store
        return dict(enabled=True,path=str(store.path),schema=1,generation=store.current.generation,opened_existing=store.opened_existing)

    def context(self):
        self.graph._ready()
        return dict(session_id=self.session_id,dataset_sha256=self.graph.dataset,generation=self._store.current.generation)

    def bootstrap(self):
        self.graph._ready()
        return self.graph._bridge.bootstrap()

    def history_details(self,fit_id):
        self.graph._ready()
        require(fit_id in self._fits,'missing_fit','Unknown fit')
        return dict(version=1,fit_id=fit_id,revision=self._revisions[fit_id],**self.history.details(fit_id))

    def _remember_versions(self):
        for key,value in self.graph._state['fit_graph']['revisions'].items():
            self.graph._revision_floor[key]=max(value,self.graph._revision_floor.get(key,0))
        ledger=self.graph._state['profiles']
        for key,row in ledger['profiles'].items():self._profile_floor[key]=max(row['revision'],self._profile_floor.get(key,0))
        for key,row in ledger['bindings'].items():self._binding_floor[key]=max(row['revision'],self._binding_floor.get(key,0))
        ledger=self.graph._state.get('targets',targets.empty())
        for key,row in ledger['profiles'].items():self._target_profile_floor[key]=max(row['revision'],self._target_profile_floor.get(key,0))
        for key,row in ledger['bindings'].items():self._target_binding_floor[key]=max(row['revision'],self._target_binding_floor.get(key,0))
        ledger=self.graph._state.get('damage_patterns',damage.empty())
        for key,row in ledger['patterns'].items():self._damage_pattern_floor[key]=max(row['revision'],self._damage_pattern_floor.get(key,0))
        for key,row in ledger['bindings'].items():self._damage_binding_floor[key]=max(row['revision'],self._damage_binding_floor.get(key,0))
        ledger=self.graph._state.get('implant_sets',implant_sets.empty())
        for key,row in ledger['sets'].items():self._implant_set_floor[key]=max(row['revision'],self._implant_set_floor.get(key,0))

    def _record_profile_action(self,before,label,participants):
        self.history=self.history.record(before,self.graph._state,label,set(participants))
        self._remember_versions()

    def _replay(self,target,redo,*,before_write=None):
        prepared,next_history,action=self.history.replay(target,redo,self.graph._state)
        # Inspect meanings before resolving any replayed relationship. A later
        # fit copy intentionally has no ordinary action, yet its live binding
        # must prevent undo-create/redo-delete or older shared-value reversal.
        old_profiles=self.graph._state['profiles']
        new_profiles=prepared['profiles']
        meaning=lambda row:None if row is None else {k:v for k,v in row.items() if k!='revision'}
        changed_profiles={key for key in set(old_profiles['profiles'])|set(new_profiles['profiles'])
                          if not damage.exact(meaning(old_profiles['profiles'].get(key)),new_profiles['profiles'].get(key))}
        profile_bound={key for ledger in (old_profiles,new_profiles) for key,row in ledger['bindings'].items()
                       if key in prepared['records'] and row['profile_id'] in changed_profiles}
        require(profile_bound<=action.participants,'history_dependency','Undo later profile assignments before this shared action')
        previous_damage=self.graph._state.get('damage_patterns',damage.empty())
        next_damage=prepared['damage_patterns']
        meaning=lambda row:None if row is None else {k:v for k,v in row.items() if k!='revision'}
        changed_damage={key for key in set(previous_damage['patterns'])|set(next_damage['patterns'])
                        if not damage.exact(meaning(previous_damage['patterns'].get(key)),next_damage['patterns'].get(key))}
        from .named_rah import holder_fits
        damage_bound=set()
        for key in changed_damage:
            damage_bound.update(holder_fits(self.graph._state['fit_graph']['records'],previous_damage,key))
            damage_bound.update(holder_fits(prepared['records'],next_damage,key))
        require(damage_bound<=action.participants,'history_dependency','Undo later damage assignments before this shared action')
        candidate=deepcopy(self.graph._state)
        deleted_set_floors={}
        deleted_damage_floors={}
        legacy=self.graph._bridge._history
        if action.legacy_token is not None:
            records,next_legacy,used=legacy.replay(target,redo,candidate['fit_graph']['records'])
            candidate['fit_graph']['records']=records
            if used:
                from android_bridge.fitting import promote
                candidate['fit_graph']['recent']=promote(self.engine,candidate['fit_graph'].get('recent',[]),used)
        else:
            next_legacy=legacy
            candidate['fit_graph']['records']=prepared['records']
            old=candidate['profiles'];candidate['profiles']=prepared['profiles']
            for key,row in candidate['profiles']['profiles'].items():
                previous=old['profiles'].get(key)
                if key.startswith('builtin:'):row['revision']=0;continue
                meaning=lambda x:{k:v for k,v in x.items() if k!='revision'}
                changed=previous is None or not _same(meaning(previous),row)
                row['revision']=advance(self._profile_floor.get(key,0)) if changed else self._profile_floor.get(key,0)
            for key,row in candidate['profiles']['bindings'].items():
                previous=old['bindings'].get(key)
                changed=previous is None or previous['profile_id']!=row['profile_id']
                profile=row['profile_id']
                profile_changed=profile not in old['profiles'] or candidate['profiles']['profiles'][profile]['revision']!=old['profiles'][profile]['revision']
                row['revision']=advance(self._binding_floor.get(key,0)) if changed or profile_changed else self._binding_floor.get(key,0)
            previous_targets=candidate.get('targets',targets.empty())
            candidate['targets']=prepared['targets']
            for key,row in candidate['targets']['profiles'].items():
                previous=previous_targets['profiles'].get(key)
                meaning=lambda value:{k:v for k,v in value.items() if k!='revision'}
                changed=previous is None or not targets.exact(meaning(previous),row)
                floor=self._target_profile_floor.get(key,0)
                row['revision']=targets.advance(floor) if changed else floor
            for key,row in candidate['targets']['bindings'].items():
                previous=previous_targets['bindings'].get(key)
                changed=previous is None or previous['target_id']!=row['target_id']
                pid=row['target_id']
                now=targets.resolve(candidate['targets'],pid)
                previous_profile=(targets.CATALOGUE.get(pid) if pid in targets.CATALOGUE else previous_targets['profiles'].get(pid))
                profile_changed=previous_profile is None or previous_profile['revision']!=now['revision']
                floor=self._target_binding_floor.get(key,0)
                row['revision']=targets.advance(floor) if changed or profile_changed else floor
            candidate['damage_patterns']=next_damage
            for key,row in next_damage['patterns'].items():
                previous=previous_damage['patterns'].get(key)
                changed=previous is None or not damage.exact(meaning(previous),row)
                floor=self._damage_pattern_floor.get(key,0)
                row['revision']=damage.advance(floor) if changed else floor
            for key,row in next_damage['bindings'].items():
                previous=previous_damage['bindings'].get(key)
                changed=previous is None or previous['pattern_id']!=row['pattern_id']
                pid=row['pattern_id']
                now=damage.resolve(next_damage,pid)
                previous_pattern=(damage.CATALOGUE.get(pid) if pid in damage.CATALOGUE else previous_damage['patterns'].get(pid))
                pattern_changed=previous_pattern is None or previous_pattern['revision']!=now['revision']
                floor=self._damage_binding_floor.get(key,0)
                row['revision']=damage.advance(floor) if changed or pattern_changed else floor
            for key in previous_damage['patterns'].keys()-next_damage['patterns'].keys():
                deleted_damage_floors[key]=damage.advance(self._damage_pattern_floor.get(key,0))
            previous_sets=candidate.get('implant_sets',implant_sets.empty())
            candidate['implant_sets']=prepared['implant_sets']
            for key,row in candidate['implant_sets']['sets'].items():
                previous=previous_sets['sets'].get(key)
                changed=previous is None or not damage.exact(meaning(previous),row)
                floor=self._implant_set_floor.get(key,0)
                row['revision']=implant_sets.advance(floor) if changed else floor
            for key in previous_sets['sets'].keys()-candidate['implant_sets']['sets'].keys():
                deleted_set_floors[key]=implant_sets.advance(self._implant_set_floor.get(key,0))
        graph=candidate['fit_graph'];records=graph['records']
        order=[key for key in graph['fit_order'] if key in records]
        order.extend(key for key in action.created_order if key in records and key not in order)
        order.extend(key for key in records if key not in order)
        graph['fit_order']=order
        graph['sample_id']=graph['sample_id'] if graph['sample_id'] in records else next(iter(order),None)
        graph['format']=1 if records else 2
        graph['revisions']={key:graph['revisions'].get(key,self.graph._revision_floor.get(key,0)) for key in records}
        graph['modified']={key:graph['modified'].get(key,0) for key in records}
        changed_profiles={key for key in set(candidate['profiles']['profiles'])|set(self.graph._state['profiles']['profiles'])
                          if candidate['profiles']['profiles'].get(key)!=self.graph._state['profiles']['profiles'].get(key)}
        bound={key for key,row in candidate['profiles']['bindings'].items() if row['profile_id'] in changed_profiles}
        require(bound<=action.participants,'history_dependency','Undo later profile assignments before this shared action')
        old_targets=self.graph._state.get('targets',targets.empty())
        new_targets=candidate.get('targets',targets.empty())
        changed_targets={key for key in set(old_targets['profiles'])|set(new_targets['profiles'])
                         if not targets.exact(old_targets['profiles'].get(key),new_targets['profiles'].get(key))}
        target_bound={key for key,row in new_targets['bindings'].items() if row['target_id'] in changed_targets}
        require(target_bound<=action.participants,'history_dependency','Undo later target assignments before this shared action')
        damage.advance(self._store.current.generation)
        named=set(action.participants)|bound|target_bound|damage_bound
        affected=BridgeSession._affected(named,self.graph._state['fit_graph']['records'],candidate['fit_graph']['records'])
        if affected & candidate['fit_graph']['records'].keys():
            damage.advance(max(self.graph._state['fit_graph'].get('modified',{}).values(),default=0))
        for key in affected & candidate['fit_graph']['records'].keys():
            damage.advance(max(self.graph._state['fit_graph']['revisions'].get(key,0),self.graph._revision_floor.get(key,0)))
        self.graph._apply_profiles(candidate)
        callback=None if before_write is None else lambda state,snapshots,changed:before_write(state,snapshots,changed,next_history)
        self.graph._commit(candidate,set(action.participants)|bound|target_bound|damage_bound,before_write=callback)
        try:
            self.graph._bridge._history=next_legacy
            self.history=next_history
            self._implant_set_floor.update(deleted_set_floors)
            self._damage_pattern_floor.update(deleted_damage_floors)
            self._remember_versions()
        except Exception:
            self._disable()
            raise

    def dispatch(self,text):
        request_id=None;observed=False
        try:
            envelope=json.loads(text,object_pairs_hook=_pairs)
            if type(envelope) is dict and type(envelope.get('request_id')) is str and 0<len(envelope['request_id'])<=128:request_id=envelope['request_id']
            self.graph._ready()
            request,named=self.graph._bridge._request(text)
            request_id=request['request_id'];operation=request['operation'];args=request['arguments']
            if operation=='snapshot':return self.graph._bridge.dispatch(text)
            self._pending_history=operation in LABELS
            legacy=self.graph._bridge._history
            before=deepcopy(self.graph._state)
            if operation=='fit_implant':
                # Equipment can atomically switch source as well as add/replace.
                # Reserve every counter before this legacy EOS staging path.
                self.graph._verify_durable()
                advance(self.history.sequence);damage.advance(self._store.current.generation)
                damage.advance(max(before['fit_graph'].get('modified',{}).values(),default=0))
                for key in BridgeSession._affected({args['fit_id']},before['fit_graph']['records'],before['fit_graph']['records']):
                    damage.advance(max(before['fit_graph']['revisions'][key],self.graph._revision_floor.get(key,0)))
            try:
                if operation in ('undo','redo'):
                    self._replay(args['fit_id'],operation=='redo')
                    observed=True
                elif operation=='set_skill_level':
                    from eos.saveddata.character import Character
                    profile_id=before['profiles']['bindings'][args['fit_id']]['profile_id']
                    profile=before['profiles']['profiles'][profile_id]
                    skill=Character.getSkillNameMap().get(args['skill'])
                    require(skill is not None,'skill','Unknown skill')
                    result=self.graph.set_profile_skill(profile_id,profile['revision'],skill.ID,args['level'],before_stage=lambda:advance(self.history.sequence))
                    observed=True
                    self._record_profile_action(before,'Change shared profile skill',set(result['affected_fits'])|{args['fit_id']})
                else:
                    result=self.graph.edit_fit(operation,args)
                    observed=True
                    current=self.graph._bridge._history
                    if operation in ('set_target_profile','set_damage_pattern'):
                        # Named binding and anonymous values are one authority;
                        # never leave a redundant ordinary history token.
                        self.graph._bridge._history=legacy
                        current=legacy
                        self._record_profile_action(before,'Change target profile' if operation=='set_target_profile' else 'Change incoming damage pattern',
                            set(result['affected_fits'])|{args['fit_id'],'library'})
                    self.history=self.history.sync_legacy(current)
                    owner=args.get('fit_id',args.get('target_id'))
                    if operation not in ('set_target_profile','set_damage_pattern') and operation in LABELS and owner in current.rows:
                        actions,cursor=current.rows[owner]
                        old_actions,old_cursor=legacy.rows.get(owner,((),0))
                        if cursor and (not old_cursor or actions[cursor-1] is not old_actions[old_cursor-1]):
                            action=actions[cursor-1]
                            self.history=self.history.record_legacy(action.label,owner,action)
                    if operation=='delete_fit':self.history=self.history.prune(set(self._fits)|{'library'})
                    self._remember_versions()
            except Exception:
                if self.graph._available:self.graph._bridge._history=legacy
                raise
            observed=True
            full=operation in {'rename_fit','duplicate_fit','delete_fit','undo','redo'}
            keys=self.graph._snapshots.keys() if full else result['affected_fits']
            return self.graph._bridge._serialize_success(request_id,[self.graph._snapshots[key] for key in keys])
        except json.JSONDecodeError:return self.graph._bridge._error(request_id,'INVALID_REQUEST','Malformed bridge request')
        except ContractError as error:return self.graph._bridge._error(request_id,error.code,str(error))
        except Exception as error:
            code='ENGINE_UNAVAILABLE' if observed or not self.graph._available or isinstance(error,StoreUncertain) else 'INVALID_EDIT'
            if code=='ENGINE_UNAVAILABLE':self._disable()
            return self.graph._bridge._error(request_id,code,'Restart to confirm saved state' if code=='ENGINE_UNAVAILABLE' else str(error))
        finally:self._pending_history=False

    def target_dispatch(self,text):
        request_id=None
        observed=False
        prepared={}
        try:
            request=targets.parse(text)
            if type(request) is dict:
                rid=request.get('request_id')
                if type(rid) is str and 0<len(rid)<=128 and all(32<=ord(c)<127 for c in rid):request_id=rid
            self.graph._ready()
            self.graph._verify_durable()
            before=deepcopy(self.graph._state)
            targets.request(request,self.context(),before['fit_graph']['records'],before.get('targets',targets.empty()))
            operation=request['operation']
            view=deepcopy(request['view'])
            fit_id=request['fit_id']
            generation=self._store.current.generation
            def prepare(state,snapshots,changed,next_history):
                context=dict(self.context(),generation=generation+(1 if changed else 0))
                target_state=targets.state_view(state,context,fit_id,view,next_history)
                encoded_state=_json(target_state)
                require(len(encoded_state.encode('utf-8'))<=targets.MAX_STATE_BYTES,
                        'response_size','Target view exceeds the bounded response size; choose another page')
                bridge=None if operation=='read' else json.loads(self.graph._bridge.bootstrap())
                prepared['text']=_json(dict(version=1,request_id=request_id,ok=True,committed=changed,
                    reopen_required=False,state=target_state,bridge=bridge,error=None))
                prepared['history']=next_history
            if operation=='read':
                prepare(before,self.graph._snapshots,False,self.history)
                self.graph._verify_durable()
            elif operation in ('undo','redo'):
                self._replay(fit_id or 'library',operation=='redo',before_write=prepare)
                observed=True
            else:
                def stage(state,snapshots,changed,selected):
                    if selected is not None:view['selected_target_id']=selected
                    named={key for key in set(before['fit_graph']['records'])|set(state['fit_graph']['records'])
                           if not targets.exact(before['fit_graph']['records'].get(key),state['fit_graph']['records'].get(key))}
                    named.update(key for key in state['fit_graph']['revisions']
                                 if state['fit_graph']['revisions'][key]!=before['fit_graph']['revisions'].get(key))
                    participants=named|{'library'}|({fit_id} if fit_id else set())
                    next_history=self.history.record(before,state,operation.replace('_',' ').capitalize()+' target profile',participants)
                    prepare(state,snapshots,changed,next_history)
                self.graph.edit_target(operation,request['arguments'],fit_id,
                    profile_floor=self._target_profile_floor,binding_floor=self._target_binding_floor,before_write=stage)
                observed=True
                self.history=prepared['history']
                self._remember_versions()
            return prepared['text']
        except Exception as error:
            uncertain=observed or not self.graph._available or isinstance(error,StoreUncertain)
            if uncertain:self._disable()
            code='reopen_required' if uncertain else getattr(error,'code','invalid_request')
            message=('Restart to confirm saved state' if uncertain else str(error) if isinstance(error,ProfileError)
                     else 'Target request could not be completed; no target changes were saved')
            message=''.join(c if targets.unicodedata.category(c)!='Cc' and not 0xD800<=ord(c)<=0xDFFF else ' ' for c in message)[:1024] or 'Target request unavailable'
            return _json(dict(version=1,request_id=request_id,ok=False,committed=None if uncertain else False,
                reopen_required=uncertain,state=None,bridge=None,error=dict(code=code,message=message)))

    def pilot_security_details(self,fit_id):
        """One read-only, context-bound view of raw source and original EOS getter."""
        from android_bridge.pilot_security import PRESETS, bound_profile, check_live, eligible, number
        self.graph._ready()
        self.graph._verify_durable()
        state=self.graph._state;graph=state['fit_graph']
        require(type(fit_id) is str and damage.FIT.fullmatch(fit_id) and fit_id in graph['records'],
                'missing_fit','Select an existing saved fit')
        self.graph._model(state['profiles'])
        binding,profile=bound_profile(state,fit_id)
        fit=self._fits[fit_id];record=graph['records'][fit_id]
        check_live(record,fit)
        pilot=record['spec']['security']['pilot']
        effective=number(fit.getPilotSecurity())
        require(effective==(profile['sec_status'] if pilot is None else pilot),
                'profile_mismatch','Effective security differs from the saved source')
        item=fit.ship.item
        require(type(item.ID) is int and item.ID>0 and type(item.name) is str and bool(item.name),
                'profile_mismatch','Hull identity is unavailable')
        available=eligible(item)
        result=dict(version=1,context=self.context(),fit_id=fit_id,revision=graph['revisions'][fit_id],
            hull_id=item.ID,hull_name=item.name,eligible=available,
            unavailable_reason=None if available else 'unsupported_hull',
            profile=dict(profile_id=binding['profile_id'],name=profile['name'],revision=profile['revision'],
                binding_revision=binding['revision'],readonly=binding['profile_id'].startswith('builtin:'),sec_status=profile['sec_status']),
            pilot=pilot,source='CHARACTER' if pilot is None else 'EXPLICIT',effective=effective,
            presets=list(PRESETS) if available else [])
        require(len(_json(result).encode('utf-8'))<=524288,'response_size','Pilot security details exceed the bounded response size')
        self.graph._verify_durable()
        return result

    def module_rah_details(self,fit_id,offset=0,limit=25):
        from .named_rah import descriptor
        from android_bridge.module_rah import GROUP
        self.graph._ready()
        self.graph._verify_durable()
        state=self.graph._state
        graph=state['fit_graph']
        require(fit_id in graph['records'],'missing_fit','Select an existing saved fit')
        damage.integer(offset)
        damage.integer(limit,1,25)
        from .named_rah import check_live
        check_live(graph['records'][fit_id],self._fits[fit_id],self.graph._bridge._rah_resolver)
        spec=graph['records'][fit_id]['spec']
        positions=[index for index,module in enumerate(spec['modules'])
                   if 'empty_slot' not in module and self.engine._item(module['name']).group.name==GROUP]
        raw=spec['damage_pattern']
        require(type(raw) is dict and set(raw)==damage.FIELDS and
                all(type(v) in (int,float) and damage.math.isfinite(v) and v>=0 for v in raw.values()) and
                damage.math.isfinite(sum(raw.values())), 'invalid_values', 'Fit pattern preview is unavailable')
        available=sum(raw.values())>0
        result=dict(version=2,context=self.context(),fit_id=fit_id,revision=graph['revisions'][fit_id],
            module_page=dict(offset=offset,limit=limit,total=len(positions),
                entries=[descriptor(state,fit_id,index,self.engine) for index in positions[offset:offset+limit]]),
            fit_pattern=dict(name='Fit pattern',available=available,
                unavailable_reason=None if available else 'zero_total',
                components={name:raw[name+'Amount'] for name in ('em','thermal','kinetic','explosive')} if available else None))
        require(len(_json(result).encode('utf-8'))<=damage.MAX_STATE_BYTES,'response_size','Reactive armor details exceed the bounded response size')
        self.graph._verify_durable()
        return result

    def damage_dispatch(self,text):
        request_id=None
        observed=False
        prepared={}
        try:
            request=damage.parse(text)
            if type(request) is dict:
                rid=request.get('request_id')
                if type(rid) is str and 0<len(rid)<=128 and all(32<=ord(c)<127 for c in rid):request_id=rid
            self.graph._ready()
            self.graph._verify_durable()
            before=deepcopy(self.graph._state)
            damage.request(request,self.context(),before['fit_graph']['records'],before.get('damage_patterns',damage.empty()))
            operation=request['operation']
            view=deepcopy(request['view'])
            fit_id=request['fit_id']
            if operation in ('module_options','set_module'):
                from .named_rah import target, check_live
                target(before,fit_id,request['arguments'],self.engine)
                check_live(before['fit_graph']['records'][fit_id],self._fits[fit_id],self.graph._bridge._rah_resolver)
            generation=self._store.current.generation
            deleted_floor=None
            if operation=='delete':
                key=request['arguments']['pattern_id']
                row=damage.resolve(before['damage_patterns'],key,revision=request['arguments']['revision'],editable=True)
                deleted_floor=damage.advance(max(row['revision'],self._damage_pattern_floor.get(key,0)))
            def prepare(state,snapshots,changed,next_history,item=None):
                context=dict(self.context(),generation=generation+(1 if changed else 0))
                module=None
                if operation in ('module_options','set_module'):
                    from .named_rah import descriptor
                    module=descriptor(state,fit_id,request['arguments']['position'],self.engine)
                damage_state=damage.state_view(state,context,fit_id,view,next_history,item=item,module=module,engine=self.engine)
                encoded_state=_json(damage_state)
                require(len(encoded_state.encode('utf-8'))<=damage.MAX_STATE_BYTES,
                        'response_size','Damage view exceeds the bounded response size; choose another page')
                bridge=None if operation in damage.READ_OPERATIONS else json.loads(self.graph._bridge.bootstrap())
                prepared['text']=_json(dict(version=3,request_id=request_id,ok=True,committed=changed,
                    reopen_required=False,state=damage_state,bridge=bridge,error=None))
                prepared['history']=next_history
            if operation in damage.READ_OPERATIONS:
                item=self.graph.damage_item_options(request['arguments'],fit_id) if operation=='item_options' else None
                prepare(before,self.graph._snapshots,False,self.history,item)
                self.graph._verify_durable()
            elif operation in ('undo','redo'):
                self._replay(fit_id or 'library',operation=='redo',before_write=prepare)
                observed=True
            else:
                def stage(state,snapshots,changed,selected,item):
                    if selected is not None:view['selected_pattern_id']=selected
                    named={key for key in set(before['fit_graph']['records'])|set(state['fit_graph']['records'])
                           if not damage.exact(before['fit_graph']['records'].get(key),state['fit_graph']['records'].get(key))}
                    named.update(key for key in state['fit_graph']['revisions']
                                 if state['fit_graph']['revisions'][key]!=before['fit_graph']['revisions'].get(key))
                    participants=named|{'library'}|({fit_id} if fit_id else set())
                    next_history=self.history.record(before,state,operation.replace('_',' ').capitalize()+' damage pattern',participants)
                    prepare(state,snapshots,changed,next_history,item)
                self.graph.edit_damage(operation,request['arguments'],fit_id,
                    pattern_floor=self._damage_pattern_floor,binding_floor=self._damage_binding_floor,before_write=stage,
                    before_stage=lambda:advance(self.history.sequence))
                observed=True
                self.history=prepared['history']
                if deleted_floor is not None:self._damage_pattern_floor[request['arguments']['pattern_id']]=deleted_floor
                self._remember_versions()
            return prepared['text']
        except Exception as error:
            uncertain=observed or not self.graph._available or isinstance(error,StoreUncertain)
            if uncertain:self._disable()
            code='reopen_required' if uncertain else getattr(error,'code','invalid_request')
            message=('Restart to confirm saved state' if uncertain else str(error) if isinstance(error,ProfileError)
                     else 'Damage request could not be completed; no damage changes were saved')
            message=''.join(c if damage.unicodedata.category(c)!='Cc' and not 0xD800<=ord(c)<=0xDFFF else ' ' for c in message)[:1024] or 'Damage request unavailable'
            return _json(dict(version=3,request_id=request_id,ok=False,committed=None if uncertain else False,
                reopen_required=uncertain,state=None,bridge=None,error=dict(code=code,message=message)))

    def implant_sets_dispatch(self,text):
        request_id=None;observed=False;prepared={}
        try:
            request=implant_sets.parse(text)
            if type(request) is dict:
                rid=request.get('request_id')
                if type(rid) is str and 0<len(rid)<=128 and all(32<=ord(c)<127 for c in rid):request_id=rid
            self.graph._ready();self.graph._verify_durable()
            before=deepcopy(self.graph._state)
            implant_sets.request(request,self.context(),before)
            operation=request['operation'];args=request['arguments'];anchor=request['anchor_fit_id']
            view=deepcopy(request['view'])
            catalogue=self.graph.implant_set_catalogue()
            generation=self._store.current.generation
            def prepare(state,snapshots,changed,next_history):
                context=dict(self.context(),generation=implant_sets.advance(generation) if changed else generation)
                value=implant_sets.state_view(state,context,anchor,view,next_history,catalogue,
                    lambda key:self.graph._bridge._fits[key].isStructure)
                require(len(_json(value).encode('utf-8'))<=implant_sets.MAX_STATE_BYTES,
                        'response_size','Implant set view exceeds the bounded response size')
                bridge=None if operation=='read' else json.loads(self.graph._bridge.bootstrap())
                prepared['text']=_json(dict(version=1,request_id=request_id,ok=True,committed=changed,
                    reopen_required=False,state=value,bridge=bridge,error=None))
                prepared['history']=next_history
            if operation=='read':
                prepare(before,self.graph._snapshots,False,self.history)
                self.graph._verify_durable()
            elif operation in ('undo','redo'):
                self._replay(view['history_target'],operation=='redo',before_write=prepare)
                observed=True
            else:
                def stage(state,snapshots,changed,selected=None):
                    if selected is not None:view['selected_set_id']=selected
                    named={key for key in state['fit_graph']['revisions']
                           if state['fit_graph']['revisions'][key]!=before['fit_graph']['revisions'].get(key)}
                    # Read-only source/anchor/template identities are not history
                    # dependencies. Shared characters retain the library timeline.
                    participants=named if operation=='apply_fit' else named|{'library'}
                    next_history=self.history.record(before,state,implant_sets.LABELS[operation],participants) if changed else self.history
                    prepare(state,snapshots,changed,next_history)
                reserve=lambda:advance(self.history.sequence)
                deleted_floor=None
                if operation=='delete':
                    row=implant_sets.resolve(before.get('implant_sets',implant_sets.empty()),args['set_id'],catalogue,
                                             revision=args['revision'],editable=True)
                    deleted_floor=implant_sets.advance_floor(row['revision'],self._implant_set_floor.get(args['set_id'],0))
                if operation=='apply_profile':
                    self.graph.apply_implant_set_profile(**args,before_write=stage,before_stage=reserve)
                else:
                    self.graph.edit_implant_set(operation,args,anchor,set_floor=self._implant_set_floor,
                                                before_write=stage,before_stage=reserve)
                observed=True
                self.history=prepared['history']
                if deleted_floor is not None:self._implant_set_floor[args['set_id']]=deleted_floor
                self._remember_versions()
            return prepared['text']
        except Exception as error:
            uncertain=observed or not self.graph._available or isinstance(error,StoreUncertain)
            if uncertain:self._disable()
            code='reopen_required' if uncertain else getattr(error,'code','invalid_request')
            if type(code) is not str or not damage.re.fullmatch('[a-z][a-z0-9_]{0,63}',code):code='invalid_request'
            message=('Restart to confirm saved state' if uncertain else str(error) if isinstance(error,ProfileError)
                     else 'Implant set request could not be completed; no changes were saved')
            message=''.join(c if damage.unicodedata.category(c)!='Cc' and not 0xD800<=ord(c)<=0xDFFF else ' ' for c in message)[:1024] or 'Implant set request unavailable'
            return _json(dict(version=1,request_id=request_id,ok=False,committed=None if uncertain else False,
                reopen_required=uncertain,state=None,bridge=None,error=dict(code=code,message=message)))

    def _guard_feature_publication(self,state):
        """Price every possible selected view once before an ordinary commit.

        Selection IDs all have the same serialized length. History counts cannot
        exceed LIMIT; existing and prospective labels come only from these
        bounded operation sets. Two maximal counts/labels intentionally reserve
        a slightly larger history than any actual cursor can publish.
        """
        # Effective commits only: no-op/replayed import paths never invoke this
        # guard, so exhausted session history cannot reject their readback.
        if self._pending_history:advance(self.history.sequence)
        labels=list(LABELS.values())+['Change shared profile skill','Change target profile',
            'Change incoming damage pattern','Import EFT fits']
        labels.extend(operation.replace('_',' ').capitalize()+' target profile' for operation in targets.OPERATIONS)
        labels.extend(operation.replace('_',' ').capitalize()+' damage pattern' for operation in damage.OPERATIONS)
        labels.extend(implant_sets.LABELS.values())
        labels.extend(operation.replace('_',' ').capitalize() for operation in
            ('create_profile','rename_profile','assign_profile','set_profile_skill','delete_profile',
             'add_profile_implant','remove_profile_implant','set_implant_source','set_pilot_security','save_profile_security'))
        labels.extend(action.label for actions,cursor in self.history.rows.values() for action in actions)
        longest=max(labels,key=lambda value:len(_json(value).encode('utf-8')))
        class PublicationHistory:
            def details(self,key):
                return dict(undo_count=LIMIT,redo_count=LIMIT,limit=LIMIT,undo_label=longest,redo_label=longest)
        context=dict(self.context(),generation=damage.advance(self._store.current.generation))
        selected=next(iter(state['fit_graph']['records']),None)
        self._feature_view(state,context,selected,PublicationHistory())

    def _feature_view(self,state,context,fit_id,history):
        from android_bridge.character_implants import display
        ledger=state['profiles'];graph=state['fit_graph']
        if fit_id is not None:require(fit_id in graph['records'],'missing_fit','Unknown fit')
        profiles=[]
        for key,row in ledger['profiles'].items():
            value=deepcopy(row);value['implants']=display(row['implants'])
            profiles.append(dict(profile_id=key,readonly=key.startswith('builtin:'),**value))
        bindings={key:dict(row,fit_revision=graph['revisions'][key],implant_source=graph['records'][key]['implant_source'])
                  for key,row in ledger['bindings'].items()}
        skills=[dict(skill_id=int(key),name=value.name) for key,value in self.graph.catalog.items()]
        result=dict(version=3,context=context,profiles=profiles,bindings=bindings,
                    skills=sorted(skills,key=lambda x:x['name']),selected_fit_id=fit_id,
                    history=history.details(fit_id or 'library'))
        require(len(_json(result).encode('utf-8'))<=524288,'response_size','Offline profiles exceed the bounded response size')
        return result

    def feature_state(self,fit_id=None):
        self.graph._ready()
        try:
            self.graph._verify_durable()
            result=self._feature_view(self.graph._state,self.context(),fit_id,self.history)
            self.graph._verify_durable()
            return result
        except StoreUncertain:
            self._disable();raise

    def feature_dispatch(self,text):
        request_id=None;observed=False;prepared={}
        try:
            request=damage.parse(text)
            require(type(request) is dict and set(request)=={'version','request_id','context','operation','arguments','anchor_fit_id'},'request','Invalid feature request')
            require(type(request['version']) is int and request['version']==3,'request','Unsupported feature version')
            request_id=damage.text(request['request_id'],128)
            self.graph._ready();self.graph._verify_durable()
            operation=request['operation'];args=request['arguments'];anchor=request['anchor_fit_id'];ctx=request['context']
            require(type(ctx) is dict and set(ctx)=={'session_id','dataset_sha256','generation'} and
                    type(ctx['session_id']) is str and damage.FIT.fullmatch(ctx['session_id']) and
                    type(ctx['dataset_sha256']) is str and damage.re.fullmatch('[0-9a-f]{64}',ctx['dataset_sha256']),
                    'request','Invalid feature context')
            damage.integer(ctx['generation'],1)
            require(damage.exact(ctx,self.context()),'stale_context','The graph changed; reload before editing')
            require(anchor is None or type(anchor) is str and damage.FIT.fullmatch(anchor) and anchor in self._fits,
                    'missing_fit','Selected fit no longer exists')
            fields={'create_profile':{'name','source'},'rename_profile':{'profile_id','revision','name'},
                    'assign_profile':{'fit_id','profile_id'},'set_profile_skill':{'profile_id','revision','skill_id','level'},
                    'delete_profile':{'profile_id','replacement'},'undo':set(),'redo':set(),
                    'add_profile_implant':{'profile_id','revision','item_id','replace_implant_id'},
                    'remove_profile_implant':{'profile_id','revision','implant_id'},
                    'set_implant_source':{'fit_id','fit_revision','source'},
                    'set_pilot_security':{'fit_id','fit_revision','pilot'},
                    'save_profile_security':{'profile_id','revision','sec_status','save_as'}}
            require(type(operation) is str and operation in fields and type(args) is dict and set(args)==fields[operation],
                    'request','Unsupported operation or fields')
            for field in ('profile_id','replacement'):
                if field in args and args[field] is not None:
                    require(type(args[field]) is str and (args[field] in ('builtin:all0','builtin:all5') or damage.re.fullmatch('profile:[0-9a-f]{32}',args[field])),
                            'identity','Invalid profile identity')
            if 'revision' in args:damage.integer(args['revision'])
            if 'fit_id' in args:
                require(type(args['fit_id']) is str and damage.FIT.fullmatch(args['fit_id']) and args['fit_id'] in self._fits,'missing_fit','Unknown fit')
            if operation in ('set_implant_source','set_pilot_security'):
                damage.integer(args['fit_revision'],1)
                require(anchor is not None and args['fit_id']==anchor,'request','Source selection must target the selected fit')
            before=deepcopy(self.graph._state)
            generation=self._store.current.generation
            def prepare(state,snapshots,changed,next_history):
                context=dict(self.context(),generation=generation+(1 if changed else 0))
                view=self._feature_view(state,context,anchor,next_history)
                prepared['text']=_json(dict(version=3,request_id=request_id,ok=True,committed=changed,
                    reopen_required=False,state=view,bridge=json.loads(self.graph._bridge.bootstrap()),error=None))
                prepared['history']=next_history
            if operation in ('undo','redo'):
                self._replay(anchor or 'library',operation=='redo',before_write=prepare)
                observed=True
            else:
                def stage(state,snapshots,changed):
                    # Library orders shared authority edits, not unrelated
                    # anchored per-fit binding/source choices. Live binding
                    # guards still block older authority reversal while used.
                    participants=({'library'} if anchor is None or operation not in ('assign_profile','set_implant_source','set_pilot_security') else set())
                    if anchor is not None:participants.add(anchor)
                    participants.update(key for key in state['fit_graph']['revisions']
                                        if state['fit_graph']['revisions'][key]!=before['fit_graph']['revisions'].get(key))
                    next_history=self.history.record(before,state,operation.replace('_',' ').capitalize(),participants) if changed else self.history
                    prepare(state,snapshots,changed,next_history)
                # Exclude known true no-ops when reserving history/generation.
                noop=(operation=='set_implant_source' and args['source']==before['fit_graph']['records'][args['fit_id']]['implant_source']) or (
                    operation=='assign_profile' and args['profile_id']==before['profiles']['bindings'][args['fit_id']]['profile_id']) or (
                    operation=='rename_profile' and args['profile_id'] in before['profiles']['profiles'] and args['name']==before['profiles']['profiles'][args['profile_id']]['name'])
                # A same scalar skill level may still remove dependent skills.
                # Detached EOS normalization decides whether this is a real edit;
                # its reservation callback runs before any live fit staging.
                if not noop and operation not in ('set_profile_skill','set_pilot_security','save_profile_security'):
                    damage.advance(generation);advance(self.history.sequence)
                if operation=='create_profile':self.graph.create_profile(args['name'],source=args['source'],before_write=stage)
                elif operation=='rename_profile':self.graph.rename_profile(args['profile_id'],args['revision'],args['name'],before_write=stage)
                elif operation=='assign_profile':self.graph.assign_profile(args['fit_id'],args['profile_id'],before_write=stage)
                elif operation=='set_profile_skill':self.graph.set_profile_skill(args['profile_id'],args['revision'],args['skill_id'],args['level'],before_write=stage,before_stage=lambda:advance(self.history.sequence))
                elif operation=='delete_profile':self.graph.delete_profile(args['profile_id'],replacement=args['replacement'],before_write=stage)
                elif operation=='add_profile_implant':self.graph.add_profile_implant(**args,before_write=stage)
                elif operation=='remove_profile_implant':self.graph.remove_profile_implant(**args,before_write=stage)
                elif operation=='set_pilot_security':self.graph.set_pilot_security(**args,before_write=stage,before_stage=lambda:advance(self.history.sequence))
                elif operation=='save_profile_security':self.graph.save_profile_security(**args,before_write=stage,before_stage=lambda:advance(self.history.sequence))
                else:self.graph.set_implant_source(**args,before_write=stage)
                observed=True
                self.history=prepared['history'];self._remember_versions()
            return prepared['text']
        except Exception as error:
            uncertain=observed or not self.graph._available or isinstance(error,StoreUncertain)
            if uncertain:self._disable()
            code='reopen_required' if uncertain else getattr(error,'code','invalid_request')
            message=('Restart to confirm saved state' if uncertain else str(error) if isinstance(error,ProfileError)
                     else 'Profile request could not be completed; no changes were saved')
            message=''.join(c if damage.unicodedata.category(c)!='Cc' and not 0xD800<=ord(c)<=0xDFFF else ' ' for c in message)[:1024] or 'Profile request unavailable'
            return _json(dict(version=3,request_id=request_id,ok=False,committed=None if uncertain else False,
                reopen_required=uncertain,state=None,bridge=None,error=dict(code=code,message=message)))

    def import_preview(self,text):
        from .eft_import import validate_request
        from .eft_specs import prepare_documents
        request_id=None
        try:
            self.graph._ready()
            request=json.loads(text,object_pairs_hook=_pairs)
            require(type(request) is dict and set(request)=={'version','request_id','profile_id','documents'},'request','Invalid preview request')
            require(type(request['version']) is int and request['version']==1,'request','Unsupported version')
            pid=request['profile_id'];profile=self.graph._state['profiles']['profiles'].get(pid)
            require(profile is not None,'profile','Select an existing profile')
            current=self._store.current
            exact=dict(version=1,operation='import_eft',request_id=request['request_id'],dataset=self.graph.dataset,
                       graph=dict(generation=current.generation,token=current.token),
                       profile=dict(id=pid,revision=profile['revision']),documents=request['documents'])
            validate_request(exact)
            request_id=exact['request_id']
            result=prepare_documents(request['documents'],self.engine)
            return _json(dict(version=1,request_id=request_id,ok=result['ok'],request=exact if result['ok'] else None,
                              documents=result['documents'],diagnostics=result['diagnostics']))
        except Exception as error:
            return _json(dict(version=1,request_id=request_id,ok=False,request=None,documents=[],diagnostics=[dict(document=None,label=None,line=0,
                              code=getattr(error,'code','invalid_request'),message=str(error))]))

    def import_execute(self,text):
        from .eft_import import import_documents,validate_request
        observed=False;request_id=None
        try:
            self.graph._ready()
            request=json.loads(text,object_pairs_hook=_pairs)
            validate_request(request)
            request_id=request['request_id']
            before=deepcopy(self.graph._state)
            self._pending_history=True
            result=import_documents(self.graph,request)
            if not result['ok']:
                if result['reopen_required']:self._disable()
                return _json(dict(version=1,request_id=request_id,ok=False,committed=result['import_committed'],
                                  reopen_required=result['reopen_required'],import_result=result,state=None,bridge=None))
            observed=True
            if not result['replayed']:
                self._record_profile_action(before,'Import EFT fits',set(result['fit_ids'])|{'library'})
            selected=next((key for key in result['fit_ids'] if key in self._fits),None)
            # Internal graph snapshots contain fit inputs; only publish existing
            # bridge snapshots plus the stable import receipt to native clients.
            result.pop('snapshot',None)
            return _json(dict(version=1,request_id=request_id,ok=True,committed=True,reopen_required=False,import_result=result,
                              state=self.feature_state(selected),bridge=json.loads(self.bootstrap())))
        except Exception as error:
            uncertain=observed or not self.graph._available or isinstance(error,StoreUncertain)
            if uncertain:self._disable()
            result=dict(version=1,operation='import_eft',ok=False,import_committed=None if uncertain else False,
                        reopen_required=uncertain,replayed=False,fit_ids=[],diagnostics=[dict(document=None,label=None,line=0,
                        code='reopen_required' if uncertain else getattr(error,'code','invalid_request'),
                        message='Reopen and retry the saved import request' if uncertain else str(error))])
            return _json(dict(version=1,request_id=request_id,ok=False,committed=result['import_committed'],reopen_required=uncertain,
                              import_result=result,state=None,bridge=None))
        finally:self._pending_history=False

    def export_preview(self,text):
        from .eft_export import render_eft
        result=dict(version=1,request_id=None,ok=False,context=None,fit_id=None,
                    revision=None,text=None,filename=None,diagnostics=[],error=None)
        try:
            self.graph._ready();result['context']=self.context()
            require(type(text) is str and len(text)<=8192,'request','Invalid export request')
            request=json.loads(text,object_pairs_hook=_pairs)
            require(type(request) is dict and set(request)=={'version','request_id','context','fit_id','revision','options'},'request','Invalid export fields')
            require(type(request['version']) is int and request['version']==1,'request','Unsupported export version')
            require(type(request['request_id']) is str and 0<len(request['request_id'])<=128 and
                    all(32<=ord(c)<127 for c in request['request_id']),'request','Invalid request identity')
            result['request_id']=request['request_id']
            key=request['fit_id'];require(type(key) is str and key in self._fits,'missing_fit','Selected fit no longer exists')
            result['fit_id']=key
            require(type(request['revision']) is int and request['revision']>=0,'request','Invalid fit revision')
            result['revision']=request['revision']
            require(_same(request['context'],self.context()) and request['revision']==self._revisions[key],
                    'stale_context','Fit changed; generate a fresh export preview')
            self.graph._verify_durable()
            rendered=render_eft(self._fits[key],request['options'])
            self.graph._verify_durable()
            result.update(rendered);result['ok']=True
        except Exception as error:
            if isinstance(error,StoreUncertain):self._disable()
            result['error']=dict(code='reopen_required' if isinstance(error,StoreUncertain) else getattr(error,'code','export_unavailable'),message=str(error))
        return _json(result)

    def capacitor_samples(self,text,cancelled=lambda:False):
        from .capacitor_samples import sample_capacitor
        handles=[]
        try:
            self.graph._ready()
            request=json.loads(text,object_pairs_hook=_pairs)
            def resolve(key):
                self.graph._ready()
                fit=self._fits[key]
                if all(fit is not old for old in handles):handles.append(fit)
                return fit,self._revisions[key]
            result=sample_capacitor(self.engine,request,resolve_fit=resolve,current_context=self.context,cancelled=cancelled,prepare_fit=self.engine.prepare_capacitor_read)
        except Exception:
            result=dict(version=1,request_id=None,ok=False,error=dict(code='invalid_request',message='Capacitor request unavailable; reopen if needed'))
        finally:
            # EOS caches one simulation per starting capacitor. Its public clear
            # API bounds that derived cache between interactive requests without
            # touching durable fit inputs or private EOS implementation fields.
            try:
                for fit in handles:fit.clear()
            except Exception:
                self.graph._available=False;self.graph._bridge._available=False
                result=dict(version=1,request_id=None,ok=False,error=dict(code='engine_error',message='Reopen after capacitor cache cleanup failure'))
        return _json(result)

    def locktime_samples(self,text,cancelled=lambda:False):
        from .locktime_samples import sample_locktime
        try:
            self.graph._ready()
            require(type(text) is str and len(text)<=16384,'request','Invalid lock-time request')
            request=json.loads(text,object_pairs_hook=_pairs)
            self.graph._verify_durable()
            def resolve(key):
                self.graph._ready()
                return self._fits[key],self._revisions[key]
            result=sample_locktime(request,resolve_fit=resolve,current_context=self.context,cancelled=cancelled,prepare_fit=self.engine.prepare_read)
            self.graph._verify_durable()
        except Exception as error:
            if isinstance(error,StoreUncertain):self._disable()
            result=dict(version=1,request_id=None,ok=False,error=dict(code='reopen_required' if isinstance(error,StoreUncertain) else getattr(error,'code','invalid_request'),message=str(error)))
        return _json(result)

    def mobility_samples(self,text,cancelled=lambda:False):
        from .mobility_samples import sample_mobility
        try:
            self.graph._ready()
            require(type(text) is str and len(text)<=16384,'request','Invalid mobility request')
            request=json.loads(text,object_pairs_hook=_pairs)
            self.graph._verify_durable()
            def resolve(key):
                self.graph._ready()
                return self._fits[key],self._revisions[key]
            result=sample_mobility(request,resolve_fit=resolve,current_context=self.context,cancelled=cancelled,prepare_fit=self.engine.prepare_read)
            self.graph._verify_durable()
        except Exception as error:
            if isinstance(error,StoreUncertain):self._disable()
            result=dict(version=1,request_id=None,ok=False,error=dict(code='reopen_required' if isinstance(error,StoreUncertain) else getattr(error,'code','invalid_request'),message=str(error)))
        return _json(result)

    def remote_repair_samples(self,text,cancelled=lambda:False):
        from .remote_repair_samples import sample_remote_repair
        # Identify only bounded, duplicate-free v2 envelopes before readiness.
        # Parsing failures are deferred so legacy readiness/error priority stays
        # unchanged. This does not validate or execute a request early.
        version, request_id = 1, None
        try:
            if type(text) is str and len(text) <= 16384:
                identified = json.loads(text, object_pairs_hook=_pairs)
                if type(identified) is dict and type(identified.get('version')) is int and identified['version'] == 2:
                    version = 2
                    value = identified.get('request_id')
                    if type(value) is str and 0 < len(value) <= 128:
                        request_id = value
        except Exception:
            pass
        try:
            self.graph._ready()
            require(type(text) is str and len(text)<=16384,'invalid_request','Invalid remote repair request')
            request=json.loads(text,object_pairs_hook=_pairs)
            self.graph._verify_durable()
            def resolve(key):
                self.graph._ready()
                return self._fits[key],self._revisions[key]
            result=sample_remote_repair(request,resolve_fit=resolve,current_context=self.context,cancelled=cancelled,prepare_fit=self.engine.prepare_read,encode=_json)
            self.graph._verify_durable()
        except Exception as error:
            if isinstance(error,StoreUncertain):self._disable()
            result=dict(version=version,request_id=request_id,ok=False,error=dict(code='reopen_required' if isinstance(error,StoreUncertain) else ('invalid_request' if isinstance(error,ContractError) and error.code=='INVALID_REQUEST' else getattr(error,'code','invalid_request')),message=str(error)))
        return result if type(result) is str else _json(result)

    def ewar_samples(self, text, cancelled=lambda:False):
        from .ewar_samples import sample_ewar, parse_request, identity, error_result
        from .ewar_resource import admit_preparation
        request_id = None
        try:
            self.graph._ready()
            request = parse_request(text)
            if type(request) is dict:
                identity(request.get('request_id'), 'request_id')
                request_id = request['request_id']
            self.graph._verify_durable()
            # The serialized bridge owns these authoritative records. Never
            # recapture or call live_records before initial G09 admission.
            bridge = self.graph._bridge
            records, fits, revisions = bridge._records, bridge._fits, bridge._revisions
            def resolve(key):
                self.graph._ready()
                return self._fits[key], self._revisions[key]
            def prep_admit(rows, handles, mode, reserve, check):
                if (bridge._records is not records or bridge._fits is not fits or
                        bridge._revisions is not revisions):
                    from android_bridge.projected_drone_admission import AdmissionRejected
                    raise AdmissionRejected('EWAR authority changed before preparation')
                return admit_preparation(records, fits, revisions, self.engine._fits,
                                         rows, handles, mode, reserve, check)
            result = sample_ewar(request, resolve_fit=resolve, current_context=self.context,
                                 cancelled=cancelled, prepare_fit=self.engine.prepare_read,
                                 prep_admit=prep_admit, encode=_json)
            self.graph._verify_durable()
        except StoreUncertain:
            self._disable()
            result = error_result(request_id, 'reopen_required', 'Reopen the fitting session after a durable-state mismatch')
        except Exception as error:
            from .capacitor_samples import SamplingError
            code = error.code if isinstance(error, (SamplingError, ProfileError)) else 'engine_error'
            result = error_result(request_id, code, 'EWAR request unavailable; no partial graph was returned')
        return result if type(result) is str else _json(result)

    def shield_regeneration_samples(self,text,cancelled=lambda:False):
        from .shield_regeneration_samples import sample_shield_regeneration
        try:
            self.graph._ready()
            require(type(text) is str and len(text)<=16384,'invalid_request','Invalid shield regeneration request')
            request=json.loads(text,object_pairs_hook=_pairs)
            self.graph._verify_durable()
            def resolve(key):
                self.graph._ready()
                return self._fits[key],self._revisions[key]
            result=sample_shield_regeneration(request,resolve_fit=resolve,current_context=self.context,cancelled=cancelled,prepare_fit=self.engine.prepare_read)
            self.graph._verify_durable()
        except Exception as error:
            if isinstance(error,StoreUncertain):self._disable()
            result=dict(version=1,request_id=None,ok=False,error=dict(code='reopen_required' if isinstance(error,StoreUncertain) else ('invalid_request' if isinstance(error,ContractError) and error.code=='INVALID_REQUEST' else getattr(error,'code','invalid_request')),message=str(error)))
        return _json(result)
