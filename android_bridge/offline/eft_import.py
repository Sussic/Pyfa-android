"""Original-text EFT import boundary; one durable commit, no trusted preview JSON.

Request identity fingerprints exact original JSON data, including text, labels,
order, dataset and expected graph/profile identities. No newline normalization.
The receipt survives edits/deletions and prevents replay from recreating fits.
"""
from copy import deepcopy
from android_bridge.projected_drone_admission import AdmissionRejected

import hashlib
import json
import re

from .eft_preview import PreviewError, require, utf8_size, MAX_DOCUMENTS, MAX_TEXT_BYTES
from .profiles import ProfileError
from .profile_store import StoreError, StoreUncertain, StoreWriteRejected
from .eft_specs import prepare_documents


def validate_request(request):
    require(type(request) is dict and set(request)=={
        'version','operation','request_id','dataset','graph','profile','documents'},
        'request','Unsupported import request fields')
    require(type(request['version']) is int and request['version']==1 and
            request['operation']=='import_eft','request','Unsupported import operation or version')
    require(type(request['request_id']) is str and
            re.fullmatch('[A-Za-z0-9_-]{1,128}',request['request_id']),
            'request','Invalid import request identity')
    require(type(request['dataset']) is str and re.fullmatch('[0-9a-f]{64}',request['dataset']),
            'request','Invalid dataset identity')
    graph,profile=request['graph'],request['profile']
    require(type(graph) is dict and set(graph)=={'generation','token'} and
            type(graph['generation']) is int and 1<=graph['generation']<2**63 and
            type(graph['token']) is str and re.fullmatch('[0-9a-f]{32}',graph['token']),
            'request','Invalid graph identity')
    require(type(profile) is dict and set(profile)=={'id','revision'} and
            type(profile['id']) is str and 0<len(profile['id'])<=128 and
            type(profile['revision']) is int and 0<=profile['revision']<2**63,
            'request','Invalid profile identity')
    documents=request['documents']
    require(type(documents) is list and 1<=len(documents)<=MAX_DOCUMENTS,
            'limit','Supply 1 to 16 EFT documents')
    total=0
    for doc in documents:
        require(type(doc) is dict and set(doc)=={'label','text'} and
                type(doc['label']) is str and 0<len(doc['label'])<=200 and
                all(ord(c)>=32 for c in doc['label']) and type(doc['text']) is str,
                'request','Invalid EFT document fields')
        utf8_size(doc['label'])
        total+=utf8_size(doc['text'])
    require(total<=MAX_TEXT_BYTES,'limit','Import text exceeds the byte limit')


def diagnostic(code,message,*,document=None,label=None,line=0):
    return dict(document=document,label=label,line=line,code=code,message=message)


def _failure(errors,committed=False,reopen=False):
    return dict(version=1,operation='import_eft',ok=False,import_committed=committed,
                reopen_required=reopen,replayed=False,fit_ids=[],diagnostics=errors)


def _success(graph,receipt,replayed):
    snapshot=graph.snapshot()
    current=graph._store.current
    return dict(version=1,operation='import_eft',ok=True,import_committed=True,
                reopen_required=False,replayed=replayed,receipt=deepcopy(receipt),
                fit_ids=list(receipt['fit_ids']),
                missing_fit_ids=[key for key in receipt['fit_ids'] if key not in snapshot['fits']],
                current_graph=dict(generation=current.generation,token=current.token),
                snapshot=snapshot,diagnostics=[])


def import_documents(graph,request):
    """Return definitive no-save, committed, or unknown/reopen outcome explicitly."""
    commit_observed=False
    try:
        validate_request(request)
        graph._ready()
        require(request['dataset']==graph.dataset,'dataset_mismatch',
                'Import dataset differs from the opened fit graph')
        fingerprint=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':'),
                                            allow_nan=False).encode('utf-8')).hexdigest()
        receipt=graph.import_receipt(request['request_id'],fingerprint)
        if receipt is not None:
            commit_observed=True
            return _success(graph,receipt,True)
        prepared=prepare_documents(request['documents'],graph.engine)
        if not prepared['ok']:
            return _failure(prepared['diagnostics'])
        result=graph.import_specs(prepared['specs'],request_id=request['request_id'],fingerprint=fingerprint,
            expected_generation=request['graph']['generation'],expected_token=request['graph']['token'],
            profile_id=request['profile']['id'],expected_profile_revision=request['profile']['revision'])
        commit_observed=True
        return _success(graph,result['receipt'],result['replayed'])
    except StoreUncertain:
        return _failure([diagnostic('persistence_uncertain','Import outcome is unknown; reopen and retry the same request')],None,True)
    except StoreWriteRejected:
        if commit_observed or not graph._available:
            return _failure([diagnostic('persistence_uncertain','Import outcome is unknown; reopen and retry the same request')],None,True)
        return _failure([diagnostic('save_rejected','Import was not saved; the previous graph is intact')])
    except AdmissionRejected as error:
        if commit_observed or not graph._available:
            return _failure([diagnostic('reopen_required','Reopen the graph before checking the import outcome')],None,True)
        return _failure([diagnostic('evaluation_budget', str(error))])
    except (ProfileError,PreviewError) as error:
        # A failure after durable confirmation is still an unknown response to the
        # caller. Do not incorrectly promise that no imported fits were saved.
        if commit_observed or not graph._available:
            return _failure([diagnostic('reopen_required','Reopen the graph before checking the import outcome')],None,True)
        docs=getattr(error,'documents',None)
        if docs is not None:
            errors=[diagnostic(error.code,str(error),document=i,label=request['documents'][i]['label'],
                               line=0) for i in docs]
        else:
            errors=[diagnostic(error.code,str(error))]
        return _failure(errors)
    except Exception:
        if commit_observed or not graph._available:
            return _failure([diagnostic('persistence_uncertain','Import outcome is unknown; reopen and retry the same request')],None,True)
        return _failure([diagnostic('engine_error','The import could not be prepared; no fits were saved')])
