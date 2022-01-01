# Maya DB style object querying

This was experimental project aimed to settle convinient serializeable protocol 
to query objects in maya scene. Unfortunately cache population take too much 
and found that serializeable protocol would be easily setup with `eval()` with 
adding some convenience:

```
import maya.cmds as mc

def ls(*args, **kwargs):
    return set(mc.ls(*args, **dict(kwargs, long=True)))
   
def get_objects(expression):
    """
    expression is a evaluatable string e.g. "ls(assemblies=True) - ls(camera=True)"
    """
    return eval(expression, globals())
```
