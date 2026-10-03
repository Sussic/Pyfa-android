"""Declarative assumptions needed to reproduce C02 output statistics."""
import math

PROFILE_FIELDS = ('emAmount','thermalAmount','kineticAmount','explosiveAmount',
                  'maxVelocity','signatureRadius','radius','hp')
RED_GIANTS = tuple(f'Class {level} Red Giant Effects' for level in range(1,7))


def profile(value):
    if value is None:
        return
    if type(value) is not dict or set(value) != set(PROFILE_FIELDS):
        raise ValueError('Invalid target profile fields')
    for key in PROFILE_FIELDS:
        amount = value[key]
        if key in ('signatureRadius','hp') and amount is None:
            continue
        if type(amount) not in (int,float) or not math.isfinite(amount):
            raise ValueError('Target profile values must be finite numbers')
        if key.endswith('Amount'):
            valid = 0 <= amount <= 1
        elif key in ('signatureRadius','hp'):
            valid = amount > 0
        else:
            valid = amount >= 0
        if not valid:
            raise ValueError('Target profile value is out of range: '+key)


def environments(rows):
    if type(rows) is not list:
        raise ValueError('Environment inputs must be a list')
    names = set()
    for row in rows:
        if type(row) is not dict or set(row) != {'name','state'}:
            raise ValueError('Invalid environment fields')
        if type(row['name']) is not str or row['name'] not in RED_GIANTS or row['name'] in names:
            raise ValueError('Unsupported or duplicate bomb environment')
        if type(row['state']) is not str or row['state'] not in ('ONLINE','OFFLINE'):
            raise ValueError('Invalid environment state')
        names.add(row['name'])


def fighters(rows):
    if type(rows) is not list:
        raise ValueError('Fighter inputs must be a list')
    for row in rows:
        if type(row) is not dict or set(row) != {'name','amount','active'}:
            raise ValueError('Invalid fighter fields')
        if type(row['name']) is not str or not row['name']:
            raise ValueError('Invalid fighter name')
        if type(row['amount']) is not int or not 1 <= row['amount'] <= 2**31-1 or type(row['active']) is not bool:
            raise ValueError('Invalid fighter amount/active state')
