import operator

import pymel.core as pm
from pyparsing import *


class ClauseExpression:

    def __init__(self, tokens):
        self.tokens = tokens

    def __repr__(self):
        return repr(self.tokens.asDict())

    def asDict(self):
        return self.tokens.asDict()


def _build_parser():
    field = Word(alphanums + '.')('field')
    operators = oneOf(['is', 'is_not', '>', '<'])('operator')
    container_operators = oneOf(['in', 'not_in'])('operator')
    value = Word(alphanums)('value')
    container_value = Suppress('(') + delimitedList(value)('value') + Suppress(
        ')')
    standard_condition = field + operators + value
    container_condition = field + container_operators + container_value
    condition = (standard_condition | container_condition)

    condition.setParseAction(ClauseExpression)
    statement = infixNotation(condition, [('not', 1, opAssoc.RIGHT),
                                          ('and', 2, opAssoc.LEFT),
                                          ('or', 2, opAssoc.LEFT)])
    return statement


Parser = _build_parser()

join_operators = {
    'and': operator.and_,
    'or': operator.or_,
}


def _populate_cache(cache, nodes=(), field=None):
    if not cache:
        cache.update({n: {'name': n.nodeName()} for n in pm.ls()})
    if field in {'allsets'}:
        _populate_cache(cache, cache.keys(), 'sets')
        _populate_cache(cache, cache.keys(), 'type')
        for k, v in cache.items():
            allsets = list(v['sets'])
            for s in allsets:
                allsets.extend(cache[s]['sets'])
            cache[k]['allsets'] = set(allsets)

    for n in nodes:
        if field in cache[n]:
            continue
        value = None
        if field == 'type':
            value = n.nodeType()
        elif field == 'types':
            value = n.nodeType(inherited=True)
        elif field == 'sets':
            if n.hasAttr('instObjGroups'):
                value = n.instObjGroups.outputs(type='objectSet')
            value = set(value or [])
            value.update(n.message.outputs(type='objectSet'))
        elif field == 'layer':
            if n.hasAttr('drawOverride'):
                value = (n.drawOverride.inputs(type='displayLayer') +
                         [None])[0]
        elif field == 'parent':
            if hasattr(n, 'getParent'):
                value = n.getParent()
        elif field == 'children':
            if hasattr(n, 'getChildren'):
                value = n.getChildren()
        elif field == 'shapes':
            if hasattr(n, 'getShapes'):
                value = n.getShapes()
            value = set(value or [])
        else:
            raise NotImplementedError('field {}'.format(field))
        cache[n][field] = value


def _handle_expression(result, cache):
    invert = False
    joinop = join_operators['and']
    _populate_cache(cache)
    objectset = cache.keys()

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
            relationship = {n: {n} for n in cache.keys()}
            for field in data['field'].split('.'):
                _populate_cache(
                    cache,
                    {cc for c in relationship.values() for cc in c if cc},
                    field)
                if field == 'name':
                    relationship = {
                        n: {cache[cc]['name'] for cc in c if cc
                           } for n, c in relationship.items()
                    }
                elif field == 'type':
                    relationship = {
                        n: {cache[cc]['type'] for cc in c if cc
                           } for n, c in relationship.items()
                    }
                elif field == 'types':
                    relationship = {
                        n:
                        {ccc for cc in c if cc
                         for ccc in cache[cc]['types']}
                        for n, c in relationship.items()
                    }
                elif field in {'sets', 'allsets'}:
                    relationship = {
                        n: {ccc for cc in c if cc
                            for ccc in cache[cc][field]}
                        for n, c in relationship.items()
                    }
                elif field == 'layer':
                    relationship = {
                        n: {
                            ccc for cc in c
                            if cc for ccc in [cache[cc][field]]
                        } for n, c in relationship.items()
                    }
                elif field == 'parent':
                    relationship = {
                        n: {
                            ccc for cc in c
                            if cc for ccc in [cache[cc][field]]
                        } for n, c in relationship.items()
                    }
                elif field == 'children':
                    relationship = {
                        n: {
                            ccc for cc in c
                            if cc for ccc in cache[cc]['children']
                        } for n, c in relationship.items()
                    }
                elif field == 'shapes':
                    relationship = {
                        n:
                        {ccc for cc in c if cc
                         for ccc in cache[cc]['shapes']}
                        for n, c in relationship.items()
                    }
                relationship = {n: c for n, c in relationship.items() if c}

            values = data['value']
            if isinstance(values, list):
                values = set(values)
            else:
                values = {values}
            if 'none' in values:
                values = values - {'none'} | {None}
            sample = {n for n, c in relationship.items() if c & values}
            if 'not' in data['operator']:
                sample = cache.keys() - sample
        else:
            sample = _handle_expression(r, cache)

        if invert:
            sample = {n for n in pm.ls() if n not in sample}
            invert = False

        objectset = joinop(objectset, sample)

    return objectset


def query(expression, cache=None):
    if cache is None:
        cache = {}
    result = Parser.parseString(expression)
    if isinstance(result[0], ClauseExpression):
        result = [result]
    return _handle_expression(result[0], cache)


if __name__ in '__main__':
    for i in [
            # 'name is persp',
            # 'name in (persp, top)',
            # 'name is top or name is persp',
            # 'name in (persp, top, front) and (name is top or name is persp)',
            # '(name in (persp, perspShape)) and (type in (camera))'
            ('type is transform and shapes.type not_in (nurbsCurve) and '
             'parent is none and shapes.type is_not camera'),
            # 'type is nurbsCurve and parent.sets.name is AnimationSet',
            # 'allsets.name is AnimationSet',
            # 'shapes.type is_not nurbsCurve and sets.name is AnimationSet',
            # 'type is displayLayer and name is layer1',
            # ('sets.name in (AnimationSet, ControlSet, FaceControlSet) and '
            #  'layer.name is_not controls'),
            # 'sets.name is set1 and layer.name is layer1',
            # 'name is root and parent is none',
            # 'parent.name is root',
            # 'parent is none',
            # 'types is dagNode',
            # 'parent.parent is none',
    ]:
        print('{}:\n\t{}'.format(i, query(i)))
