import logging
import operator
import time
import re

from maya import cmds  # NOTE pymel was slow in 20 times
from pyparsing import (
    alphanums,
    delimitedList,
    Forward,
    infixNotation,
    oneOf,
    opAssoc,
    quotedString,
    removeQuotes,
    Suppress,
    Word,
)


logger = logging.getLogger(__name__)


class ClauseExpression:

    def __init__(self, tokens):
        self.tokens = tokens

    def __repr__(self):
        return repr(self.tokens.asDict())

    def asDict(self):
        return self.tokens.asDict()


def _build_parser():
    field = Word(alphanums + '.:')('field')
    operators = oneOf(['is', 'is_not', 'match'])('operator')
    container_operators = oneOf(['in', 'not_in'])('operator')
    relationship_operators = oneOf(['has'])('operator')
    value = Word(alphanums)('value')
    quoted_value = quotedString('value').setParseAction(removeQuotes)
    container_value = Suppress('(') + delimitedList(value)('value') + Suppress(
        ')')
    standard_condition = field + operators + (value | quoted_value)
    container_condition = field + container_operators + container_value
    forward = Forward()
    relationship_condition = field + relationship_operators + (
        Suppress('(') + forward('value') + Suppress(')'))
    condition = (standard_condition | container_condition |
                 relationship_condition)

    condition.setParseAction(ClauseExpression)
    statement = infixNotation(condition, [('not', 1, opAssoc.RIGHT),
                                          ('and', 2, opAssoc.LEFT),
                                          ('or', 2, opAssoc.LEFT)])
    forward <<= statement
    return statement


Parser = _build_parser()

join_operators = {
    'and': operator.and_,
    'or': operator.or_,
}

value_mapping = {
    'none': None,
    'false': False,
    'true': True,
}


def _populate_cache(cache, nodes=(), field=None):
    if not cache:
        ls = cmds.ls(showType=True, long=True)
        for n, t in zip(ls[::2], ls[1::2]):
            cache[n] = {'name': n.split('|')[-1], 'type': t, 'path': n}
        # something weird after listRelatives, so prevent that
        cache['initialShadingGroup']['parent'] = None
    if field in {'allsets'}:
        _populate_cache(cache, cache.keys(), 'sets')
        for k, v in cache.items():
            allsets = list(v['sets'])
            for s in allsets:
                allsets.extend(cache[s]['sets'])
            cache[k]['allsets'] = set(allsets)
        return
    elif field == 'default':
        for n in cache.keys():
            cache[n][field] = False
        for n in cmds.ls(defaultNodes=True, long=True) + [
                # exceptions
                '|persp',
                '|persp|perspShape',
                '|top',
                '|top|topShape',
                '|front',
                '|front|frontShape',
                '|side',
                '|side|sideShape',
        ]:
            cache[n][field] = True
        return
    elif field == 'referenced':
        for n in cache.keys():
            cache[n][field] = False
        for n in cmds.ls(referencedNodes=True, long=True):
            cache[n][field] = True
        return
    elif field == 'layer':
        for n in cache.keys():
            cache[n][field] = None
        items = {
            n: c for c in cmds.ls(type='displayLayer', long=True)
            for n in cmds.ls(
                cmds.listConnections(c + '.drawInfo', d=True, s=False) or [],
                long=True)
        }
        for n, l in sorted(items.items(), reverse=True):
            for k, v in cache.items():
                if k.startswith(n):
                    v[field] = l
        return

    for n in nodes:
        if field in cache[n]:
            continue
        value = None
        if field == 'types':
            value = cmds.nodeType(n, inherited=True)
        elif field == 'sets':
            if cmds.attributeQuery('instObjGroups', node=n, exists=True):
                value = cmds.listConnections(n + '.instObjGroups',
                                             d=True,
                                             s=False,
                                             type='objectSet')
            value = set(value if value else [])
            value.update(
                cmds.listConnections(
                    n + '.message', d=True, s=False, type='objectSet') or [])
        elif field == 'parent':
            value = cmds.listRelatives(n, fullPath=True, parent=True)
            if value:
                value = value[0]
        elif field == 'children':
            value = cmds.listRelatives(n, fullPath=True, children=True)
            value = set(value if value else [])
        elif field == 'shapes':
            value = cmds.listRelatives(n, fullPath=True, shapes=True)
            value = set(value if value else [])
        else:
            if field.startswith('attr:'):
                attr = field[len('attr:'):]
                if cmds.attributeQuery(attr, node=n, exists=True):
                    # normalize to strings
                    value = cmds.getAttr(n + '.' + attr)
                    if not isinstance(value, (bool)):
                        value = str(value)
            else:
                raise NotImplementedError('field {!r}'.format(field))
        cache[n][field] = value


def _handle_expression(result, objectset, cache):
    if isinstance(result, ClauseExpression):
        result = [result]

    invert = False
    joinop = join_operators['and']
    _populate_cache(cache)
    if objectset is None:
        objectset = cache.keys()
    resultset = objectset

    for r in result:
        if r == 'not':
            invert = True
            continue
        if r in join_operators.keys():
            joinop = join_operators[r]
            continue

        if isinstance(r, ClauseExpression):
            data = r.asDict()
            # set of object relationships according to criteria
            relationship = {n: {n} for n in objectset}
            for field in data['field'].split('.'):
                _populate_cache(
                    cache,
                    {cc for c in relationship.values() for cc in c if cc},
                    field)
                if field in {'name', 'type'}:
                    relationship = {
                        n: {cache[cc][field] for cc in c if cc
                            } for n, c in relationship.items()
                    }
                elif field in {
                        'allsets', 'children', 'sets', 'shapes', 'types'
                }:
                    relationship = {
                        n: {ccc for cc in c if cc
                            for ccc in cache[cc][field]}
                        for n, c in relationship.items()
                    }
                else:
                    relationship = {
                        n:
                        {ccc for cc in c if cc
                         for ccc in [cache[cc][field]]}
                        for n, c in relationship.items()
                    }
                relationship = {n: c for n, c in relationship.items() if c}

            if data['operator'] == 'match':
                pattern = re.compile(data['value'])
                sample = set()
                for n, c in relationship.items():
                    for cc in c:
                        if pattern.match(cc):
                            sample.add(n)
                            break
            elif data['operator'] == 'has':
                relationship_sample = _handle_expression(
                    data['value'],
                    {cc for c in relationship.values() for cc in c}, cache)
                sample = {
                    n for n, c in relationship.items()
                    if c & relationship_sample
                }
            else:
                values = data['value']
                values = set(values) if isinstance(values, list) else {values}
                for v in values:
                    if v.lower() in value_mapping:
                        values = values - {v} | {value_mapping[v.lower()]}

                sample = {n for n, c in relationship.items() if c & values}
            if 'not' in data['operator']:
                invert = not invert
        else:
            sample = _handle_expression(r, objectset, cache)

        if invert:
            sample = objectset - sample
            invert = False

        resultset = joinop(resultset, sample)

    return resultset


def query(expression, cache=None):
    if cache is None:
        cache = {}
    result = Parser.parseString(expression)
    return _handle_expression(result, None, cache)


if __name__ in '__main__':
    cache = {}
    # cache['IKExtracvSpine1_M_rotateY']
    # cmds.listRelatives('initialShadingGroup', fullPath=True, parent=True)
    for i in [
            # 'name is persp',
            # 'name is persp',
            # 'name is persp and name is persp',
            # 'name is persp and name is persp and name is persp',
            # 'name in (persp, top)',
            # 'name is top or name is persp',
            # 'name in (persp, top, front) and (name is top or name is persp)',
            # '(name in (persp, perspShape)) and (type in (camera))',
            # ('type is transform and shapes.type not_in (nurbsCurve) and '
            #  'parent is none and shapes.type is_not camera'),
            # 'type is nurbsCurve and parent.sets.name is AnimationSet',
            # 'allsets.name is QuickSets',
            # 'shapes.type is_not nurbsCurve and allsets.name is AnimationSet',
            # 'type is displayLayer and name is layer1',
            # ('sets.name in (AnimationSet, ControlSet, FaceControlSet) and '
            #  'layer.name is_not controls'),
            # ('allsets.name is all1 and layer.name is_not controls '
            #  'and type is_not objectSet'),
            # 'name is root and parent is none',
            # 'parent.name is root',
            # 'parent is none',
            # 'types is dagNode',
            # 'parent.parent is none',
            # 'parent is_not none and default is true',
            # 'default is true and referenced is false',
            # 'attr:displaySmoothMesh not_in (0, none)',
            # 'name match "[a-zA-Z0-9]+"',
            # 'parent.name match "[a-zA-Z]+\d"',
            ('parent.shapes has (attr:intermediateObject is true '
             'and referenced is true)'),
    ]:
        start = time.time()
        print(i)
        nodes = query(i, cache=cache)
        print('\t{:.3f} {}'.format(time.time() - start, nodes))
