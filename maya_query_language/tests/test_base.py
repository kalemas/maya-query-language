from maya_query_language import query
import pymel.core as pm

def test_nodes():
    assert not query('default is false')
    pm.createNode('transform', name='root')
    pm.createNode('transform', name='mesh', parent='root')
    pm.createNode('mesh', name='meshShape', parent='mesh')
    assert query('type is mesh') == {'|root|mesh|meshShape'}
    assert query('name is mesh') == {'|root|mesh'}
    pm.createNode('objectSet', name='childSet')
    pm.sets('childSet', add='mesh')
    assert query('sets.name is childSet') == {'|root|mesh'}
    pm.createNode('objectSet', name='rootSet')
    pm.sets('rootSet', add=['childSet', 'root'])
    assert query('allsets.name is rootSet') == {
        '|root|mesh', '|root', 'childSet'
    }
    assert query('parent.parent.name is root') == {'|root|mesh|meshShape'}
