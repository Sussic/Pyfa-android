# =============================================================================
# EFT line grammar adapted from Pyfa service/port/eft.py, Copyright (C) 2014
# Ryan Holmes. Pyfa is free software under GNU GPL version 3 or later, without
# warranty. See https://www.gnu.org/licenses/gpl-3.0.html and upstream COPYING.
# =============================================================================
"""I01 headless text preflight. This module cannot create or persist a fit.

Preview retains source sections and resolved identities for the later EOS import
transaction. A successful preview proves syntax and lookup only, not rack
classification, fitting legality, import support, or numerical/native parity.
CFG, mutations, export and clipboard/file plumbing remain separate work.
"""
from copy import deepcopy
import json
import re
import threading

MAX_DOCUMENTS = 16
MAX_TEXT_BYTES = 1024 * 1024
MAX_LINES = 10000
MAX_LINE_CHARS = 1024
MAX_QUANTITY = 2**31 - 1
NAME_CHARS = r'[^,/\[\]]'
ITEM = re.compile(r'^(?P<typeName>{0}+?)(,\s*(?P<chargeName>{0}+?))?(?P<offline>\s*/(OFFLINE|offline))?(\s*\[(?P<mutation>\d+?)\])?$'.format(NAME_CHARS))
QUANTITY = re.compile(r'^(?P<typeName>{}+?) x(?P<amount>\d+?)(\s*\[(?P<mutation>\d+?)\])?$'.format(NAME_CHARS))
HEADER = re.compile(r'\[(?P<shipType>[^,\[\]]+),\s*(?P<fitName>.+)\]')
EMPTY = re.compile(r'\[Empty (Low|Med|High|Rig|Subsystem|Service) slot\]')


class PreviewError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def require(condition, code, message):
    if not condition:
        raise PreviewError(code, message)


def utf8_size(value):
    try:
        return len(value.encode('utf-8'))
    except UnicodeEncodeError as error:
        raise PreviewError('encoding', 'Text contains an invalid Unicode scalar') from error


def parse_text(text):
    """Return syntax tokens and located errors; never discard an unrecognized line."""
    require(type(text) is str, 'request', 'EFT text must be a string')
    size = utf8_size(text)
    require(size <= MAX_TEXT_BYTES, 'limit', 'EFT text exceeds the byte limit')
    # Validate before strip/splitting can erase controls. Accept CR/LF line
    # endings and tabs for outer indentation; interior tabs are rejected below.
    require(not any((ord(c) < 32 and c not in '\t\r\n') or 127 <= ord(c) <= 159 for c in text),
            'encoding', 'EFT text contains a forbidden control character')
    lines = text.removeprefix('\ufeff').replace('\r\n','\n').replace('\r','\n').split('\n')
    require(len(lines) <= MAX_LINES, 'limit', 'EFT text exceeds the line limit')
    errors = []
    tokens = []
    header = None
    section = 0
    pending_blank = False
    def error(number, code, message):
        errors.append(dict(line=number, code=code, message=message))
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if len(raw) > MAX_LINE_CHARS:
            error(number, 'limit', 'EFT line exceeds the character limit')
            tokens.append(dict(kind='invalid', line=number, section=section, text=raw[:MAX_LINE_CHARS]))
            continue
        if not line:
            if header is not None and tokens: pending_blank = True
            continue
        if any(ord(c) < 32 for c in line):
            error(number, 'encoding', 'EFT line contains a control character')
            tokens.append(dict(kind='invalid', line=number, section=section, text=line))
            continue
        if header is None:
            match = HEADER.fullmatch(line)
            if match and match['shipType'].strip() and match['fitName'].strip():
                header = dict(ship=match['shipType'].strip(), name=match['fitName'].strip(), line=number)
            else:
                error(number, 'header', 'Expected [ship, fit name] header')
                tokens.append(dict(kind='invalid', line=number, section=section, text=line))
            continue
        if pending_blank:
            section += 1
            pending_blank = False
        common = dict(line=number, section=section, text=line)
        empty = EMPTY.fullmatch(line)
        if empty:
            tokens.append(dict(common, kind='empty', slot=empty[1].upper()))
            continue
        if HEADER.fullmatch(line):
            error(number, 'multiple_fits', 'Provide each fitting as a separate document')
            tokens.append(dict(common, kind='invalid'))
            continue
        if re.search(r'\[\d+\]', line):
            error(number, 'unsupported_mutation', 'Mutation data requires the later mutation import path')
            tokens.append(dict(common, kind='invalid'))
            continue
        match = QUANTITY.fullmatch(line)
        if match:
            amount = int(match['amount'])
            if not 1 <= amount <= MAX_QUANTITY:
                error(number, 'quantity', 'Quantity must be a positive 32-bit integer')
                tokens.append(dict(common, kind='invalid'))
            else:
                tokens.append(dict(common, kind='quantity', name=match['typeName'].strip(), amount=amount))
            continue
        match = ITEM.fullmatch(line)
        if match and match['typeName'].strip() and (match['chargeName'] is None or match['chargeName'].strip()):
            tokens.append(dict(common, kind='item', name=match['typeName'].strip(),
                charge=match['chargeName'].strip() if match['chargeName'] else None,
                offline=bool(match['offline'])))
            continue
        error(number, 'syntax', 'Malformed or unsupported EFT line')
        tokens.append(dict(common, kind='invalid'))
    if header is None and not errors: error(0, 'empty', 'No fitting text was supplied')
    return dict(header=header, tokens=tokens, diagnostics=errors)


def _metadata(value):
    require(type(value) is dict and set(value) == {'id', 'name', 'category'},
            'catalog', 'Item resolver returned unsupported metadata')
    require(type(value['id']) is int and value['id'] > 0 and type(value['name']) is str
            and bool(value['name']) and type(value['category']) is str and bool(value['category']),
            'catalog', 'Item resolver returned invalid metadata')
    utf8_size(value['name'])
    utf8_size(value['category'])
    return deepcopy(value)


def preview(request, resolve):
    """Strict typed batch boundary. Partial previews are always marked as failed.

    Resolve is an offline catalogue lookup only. The function has no store/engine
    mutation capability. Tokens and complete diagnostics remain visible on error.
    """
    require(type(request) is dict and set(request) == {'version', 'operation', 'documents'},
            'request', 'Unsupported preview request fields')
    require(type(request['version']) is int and request['version'] == 1 and
            request['operation'] == 'preview_eft', 'request', 'Unsupported preview operation or version')
    documents = request['documents']
    require(type(documents) is list and 1 <= len(documents) <= MAX_DOCUMENTS,
            'limit', 'Supply between 1 and 16 EFT documents')
    total = 0
    for document in documents:
        require(type(document) is dict and set(document) == {'label', 'text'},
                'request', 'Invalid document fields')
        require(type(document['label']) is str and 0 < len(document['label']) <= 200
                and all(ord(c) >= 32 for c in document['label']), 'request', 'Invalid document label')
        utf8_size(document['label'])
        require(type(document['text']) is str, 'request', 'Document text must be a string')
        try: total += len(document['text'].encode('utf-8'))
        except UnicodeEncodeError as error: raise PreviewError('encoding', 'Invalid Unicode text') from error
    require(total <= MAX_TEXT_BYTES, 'limit', 'Batch text exceeds the byte limit')
    results = []
    diagnostics = []
    cache = {}
    for index, document in enumerate(documents):
        try:
            parsed = parse_text(document['text'])
        except PreviewError as error:
            parsed = dict(header=None, tokens=[], diagnostics=[dict(line=0,code=error.code,message=str(error))])
        def lookup(item_name, line, *, role):
            if item_name not in cache:
                try:
                    found = resolve(item_name)
                    cache[item_name] = _metadata(found) if found is not None else None
                except Exception:
                    # Don't expose local exception paths or treat a broken catalogue as unknown.
                    cache[item_name] = False
            value = cache[item_name]
            if value is False:
                parsed['diagnostics'].append(dict(line=line,code='catalog_unavailable',message='Offline item lookup failed'))
                return None
            if value is None:
                parsed['diagnostics'].append(dict(line=line,code='unknown_item',message=f'Unknown {role}: {item_name}'))
                return None
            if role == 'hull' and value['category'] not in ('Ship', 'Structure'):
                parsed['diagnostics'].append(dict(line=line,code='hull_category',message='Header item is not a ship or structure'))
            if role == 'charge' and value['category'] != 'Charge':
                parsed['diagnostics'].append(dict(line=line,code='charge_category',message='Loaded charge is not in the Charge category'))
            return deepcopy(value)
        if parsed['header']:
            h = parsed['header']
            h['item'] = lookup(h['ship'],h['line'],role='hull')
        for token in parsed['tokens']:
            if token['kind'] in ('item','quantity'):
                token['item'] = lookup(token['name'],token['line'],role='item')
                if token['kind']=='item' and token['charge']:
                    token['charge_item'] = lookup(token['charge'],token['line'],role='charge')
        for error in parsed.pop('diagnostics'):
            diagnostics.append(dict(error,document=index,label=document['label']))
        results.append(dict(parsed,label=document['label'],document=index))
    return dict(version=1,operation='preview_eft',ok=not diagnostics,
        scope='syntax_and_item_lookup_only',import_committed=False,documents=results,diagnostics=diagnostics)


def dispatch_json(payload, resolve):
    """JSON wire boundary with duplicate/nonfinite/oversized input rejection."""
    try:
        require(type(payload) is str and len(payload.encode('utf-8')) <= 2*MAX_TEXT_BYTES,
                'limit', 'Invalid or oversized JSON request')
        def pairs(items):
            result={}
            for key,value in items:
                require(key not in result,'request','Duplicate JSON field')
                result[key]=value
            return result
        def nonfinite(value): raise PreviewError('request','Nonfinite JSON number')
        request=json.loads(payload,object_pairs_hook=pairs,parse_constant=nonfinite)
        result=preview(request,resolve)
    except (PreviewError, ValueError, TypeError, RecursionError) as error:
        result=dict(version=1,operation='preview_eft',ok=False,scope='syntax_and_item_lookup_only',
            import_committed=False,documents=[],diagnostics=[dict(document=None,label=None,line=0,
            code=error.code if isinstance(error,PreviewError) else 'request',
            message=str(error) if isinstance(error,PreviewError) else 'Invalid JSON request')])
    return json.dumps(result,ensure_ascii=False,separators=(',',':'),allow_nan=False)


class EosResolver:
    """Already-initialized EOS catalogue, same worker; no GUI, network or fit access.

    Lookup does not establish desktop publicity/availability policy. That policy,
    section classification and module legality belong to the next import stage.
    """
    def __init__(self): self._thread=threading.get_ident()

    def __call__(self, item_name):
        require(threading.get_ident()==self._thread,'thread','Use the owning EOS worker')
        import eos.db
        item=eos.db.getItem(item_name)
        return None if item is None else dict(id=item.ID,name=item.typeName,category=item.category.name)
