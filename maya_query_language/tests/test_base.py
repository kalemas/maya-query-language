from maya_query_language import query
import pymel.core as pm
import pytest

@pytest.fixture(scope='session')
def simplescene():
    pm.createNode('transform', name='root')
    pm.createNode('transform', name='mesh', parent='root')
    pm.createNode('mesh', name='meshShape', parent='mesh')
    pm.createNode('objectSet', name='childSet')
    pm.sets('childSet', add='mesh')
    pm.createNode('objectSet', name='rootSet')
    pm.sets('rootSet', add=['childSet', 'root'])


@pytest.fixture(scope='session')
def complexscene(simplescene):
    pass


def test_empty():
    assert not query('default is false')


def test_simplescene(simplescene):
    assert query('type is mesh') == {'|root|mesh|meshShape'}
    assert query('name is mesh') == {'|root|mesh'}
    assert query('sets.name is childSet') == {'|root|mesh'}
    assert query('allsets.name is rootSet') == {
        '|root|mesh', '|root', 'childSet'
    }
    assert query('parent.parent.name is root') == {'|root|mesh|meshShape'}

def test_simplescene_has(simplescene):
    assert query('parent.parent has (name is root and parent is none)') == {
        '|root|mesh|meshShape'
    }
