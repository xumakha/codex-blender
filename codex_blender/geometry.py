"""Expand native Blender assembly recipes into explicit, independently animatable parts."""
from copy import deepcopy
import os

MAX_EXPANDED_OBJECTS = 4000


def expand_objects(objects, limit=None):
    if limit is None:
        limit = max(1, int(os.environ.get('CODEX_BLENDER_OBJECT_BUDGET', MAX_EXPANDED_OBJECTS)))
    children = {}
    names = {obj['name'] for obj in objects}
    if len(names) != len(objects):
        raise ValueError('Duplicate geometry object names')
    for obj in objects:
        parent = obj.get('parent')
        if parent is not None and parent not in names:
            raise ValueError('Geometry parent does not exist')
        children.setdefault(parent, []).append(obj)
    result = []
    visited = set()

    def visit(template, parent, suffix, chain):
        if template['name'] in chain:
            raise ValueError('Geometry hierarchy contains a cycle')
        visited.add(template['name'])
        repeat = template.get('repeat') or {'count':1,'offset':[0,0,0],'rotation':[0,0,0]}
        for index in range(repeat['count']):
            tag = suffix + (f'__R{len(chain)}_{index}' if index else '')
            obj = {**template, 'keyframes': deepcopy(template.get('keyframes', []))}
            obj['name'], obj['parent'], obj['repeat'] = template['name']+tag, parent, None
            for prop, delta in (('location', repeat['offset']), ('rotation', repeat['rotation'])):
                obj[prop] = [value+index*step for value,step in zip(obj[prop],delta)]
                for key in obj.get('keyframes',[]):
                    if key.get(prop) is not None:
                        key[prop] = [value+index*step for value,step in zip(key[prop],delta)]
            if len(obj['name'].encode('utf-8'))>59:
                raise ValueError('Use shorter object identifiers for repeated geometry')
            result.append(obj)
            if len(result)>limit:
                raise ValueError(f'The expanded shot exceeds {limit} objects; simplify its assembly')
            for child in children.get(template['name'],[]):
                visit(child,obj['name'],tag,chain | {template['name']})

    for root in children.get(None,[]):
        visit(root,None,'',set())
    if visited != names:
        raise ValueError('Geometry hierarchy contains an unreachable cycle')
    return result


def descendants(objects, roots):
    names = set(roots)
    while True:
        expanded = names | {obj['name'] for obj in objects if obj.get('parent') in names}
        if names == expanded:
            return names
        names = expanded


def recipe_instances(templates, roots, parts=False):
    """Count visible modeled parts, including repeated groups and descendants."""
    expanded = expand_objects(templates)
    selected = set(roots)
    if parts:
        physical = {obj['name'] for obj in templates if obj['name'] in selected and obj['kind'] not in ('empty','image')}
        if physical:
            return [obj for obj in expanded if obj['name'].split('__R',1)[0] in physical and max(abs(value) for value in obj['scale'])>.001]
        # A compound part such as a floor/flight/head is represented by its group instances.
        # Nested body parts and steps belong to it without becoming duplicate parts themselves.
        groups = {obj['name'] for obj in templates if obj['name'] in selected and obj['kind']=='empty'}
        modeled_groups = {name for name in groups if any(obj['name'] in descendants(templates,[name]) and obj['kind'] not in ('empty','image') for obj in templates)}
        return [obj for obj in expanded if obj['name'].split('__R',1)[0] in modeled_groups]
    selected = descendants(templates,selected)
    instances = []
    for obj in expanded:
        original = obj['name'].split('__R',1)[0]
        if original in selected and obj['kind'] not in ('empty','image'):
            if max(abs(value) for value in obj['scale']) > .001:
                instances.append(obj)
    return instances
