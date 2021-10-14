import maya_query_language
import pymel.core as pm

def test_nodes():
    assert not maya_query_language.query('default is false')
    pm.createNode('transform', name='root')
    pm.createNode('transform', name='mesh', parent='root')
    pm.createNode('mesh', name='meshShape', parent='mesh')
    assert maya_query_language.query('type is mesh') == {
        '|root|mesh|meshShape'}
