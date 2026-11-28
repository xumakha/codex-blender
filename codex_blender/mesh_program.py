"""Evaluate a bounded Python subset that returns mesh data, without executing Python code."""
import ast
import math
import operator
import os


MAX_VERTICES = 50_000
MAX_FACES = 50_000
MAX_FACE_SIZE = 256
FUNCTIONS = {name: getattr(math, name) for name in
             ('sin', 'cos', 'tan', 'sqrt', 'atan2', 'floor', 'ceil', 'radians')}
FUNCTIONS.update(abs=abs, min=min, max=max, range=range)
OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
             ast.Div: operator.truediv, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv,
             ast.Pow: operator.pow}
COMPARISONS = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt,
               ast.GtE: operator.ge, ast.Eq: operator.eq, ast.NotEq: operator.ne}


def mesh_budget():
    return max(1, int(os.environ.get('CODEX_BLENDER_MESH_BUDGET', '2000000')))


def build_mesh(program):
    """Programs can assign variables and construct vertices/faces with numeric comprehensions."""
    if len(program) > 24_000:
        raise ValueError('Mesh program is too large')
    budget = mesh_budget()
    env = {'pi': math.pi, 'tau': math.tau}

    def number(value):
        if type(value) not in (int, float) or abs(value) > 1e9 or not math.isfinite(value):
            raise ValueError('Expected a finite number within +/-1e9')
        return value

    def bind(target, value, scope):
        if isinstance(target, ast.Name):
            scope[target.id] = value
            return
        if not isinstance(target, (ast.List, ast.Tuple)) or not isinstance(value, (tuple, range)):
            raise ValueError('Mesh comprehension targets must be local names or tuples of names')
        if len(target.elts) != len(value):
            raise ValueError('Mesh comprehension tuple has the wrong number of values')
        for item, entry in zip(target.elts, value):
            bind(item, entry, scope)

    def evaluate(expr, scope):
        nonlocal budget
        budget -= 1
        if budget < 0:
            raise ValueError('Mesh program exceeded its operation budget')
        if isinstance(expr, ast.Constant):
            return number(expr.value)
        if isinstance(expr, ast.Name):
            if expr.id not in scope:
                raise ValueError(f'Undefined mesh variable: {expr.id}')
            return scope[expr.id]
        if isinstance(expr, (ast.List, ast.Tuple)):
            return tuple(evaluate(item, scope) for item in expr.elts)
        if isinstance(expr, ast.UnaryOp) and isinstance(expr.op, (ast.UAdd, ast.USub)):
            value = number(evaluate(expr.operand, scope))
            return -value if isinstance(expr.op, ast.USub) else value
        if isinstance(expr, ast.BinOp) and type(expr.op) in OPERATORS:
            left, right = evaluate(expr.left, scope), evaluate(expr.right, scope)
            if isinstance(expr.op, ast.Add) and isinstance(left, tuple) and isinstance(right, tuple):
                if len(left) + len(right) > MAX_VERTICES:
                    raise ValueError('Mesh sequence is too large')
                budget -= len(left) + len(right)
                if budget < 0:
                    raise ValueError('Mesh program exceeded its operation budget')
                return left + right
            left, right = number(left), number(right)
            if isinstance(expr.op, ast.Pow) and abs(right) > 32:
                raise ValueError('Mesh exponent exceeds +/-32')
            return number(OPERATORS[type(expr.op)](left, right))
        if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and not expr.keywords:
            function = FUNCTIONS.get(expr.func.id)
            if function is not None:
                args = [number(evaluate(arg, scope)) for arg in expr.args]
                result = function(*args)
                if isinstance(result, range):
                    if len(result) > MAX_VERTICES:
                        raise ValueError('Mesh loop range is too large')
                    return result
                return number(result)
        if isinstance(expr, ast.Subscript):
            sequence = evaluate(expr.value, scope)
            index = evaluate(expr.slice, scope)
            if isinstance(sequence, (tuple, range)) and type(index) is int:
                return sequence[index]
        if isinstance(expr, ast.Compare) and len(expr.ops) == 1 and type(expr.ops[0]) in COMPARISONS:
            left = number(evaluate(expr.left, scope))
            right = number(evaluate(expr.comparators[0], scope))
            return COMPARISONS[type(expr.ops[0])](left, right)
        if isinstance(expr, ast.IfExp):
            return evaluate(expr.body if evaluate(expr.test, scope) else expr.orelse, scope)
        if isinstance(expr, ast.ListComp) and 1 <= len(expr.generators) <= 3:
            if all(not gen.is_async for gen in expr.generators):
                result = []

                def append(index, local):
                    if index == len(expr.generators):
                        if len(result) >= MAX_VERTICES:
                            raise ValueError('Mesh comprehension output is too large')
                        result.append(evaluate(expr.elt, local))
                        return
                    gen = expr.generators[index]
                    sequence = evaluate(gen.iter, local)
                    if not isinstance(sequence, (range, tuple)):
                        raise ValueError('Mesh comprehensions must iterate over range(), lists or tuples')
                    for value in sequence:
                        nested = local.copy()
                        bind(gen.target, value, nested)
                        if all(evaluate(test, nested) for test in gen.ifs):
                            append(index + 1, nested)

                append(0, scope)
                return tuple(result)
        raise ValueError(f'Unsupported mesh program expression: {type(expr).__name__}')

    try:
        tree = ast.parse(program)
        for statement in tree.body:
            if (not isinstance(statement, ast.Assign) or len(statement.targets) != 1
                    or not isinstance(statement.targets[0], ast.Name)):
                raise ValueError('Mesh programs only support assignments to local variables')
            env[statement.targets[0].id] = evaluate(statement.value, env)
        return validate_mesh(env.get('vertices'), env.get('faces'))
    except (ArithmeticError, SyntaxError, TypeError, IndexError, RecursionError) as exc:
        raise ValueError(f'Invalid mesh program: {exc}') from exc


def validate_mesh(vertices, faces):
    if not isinstance(vertices, (list, tuple)) or not 3 <= len(vertices) <= MAX_VERTICES:
        raise ValueError('Mesh needs between 3 and 50000 vertices')
    if not isinstance(faces, (list, tuple)) or not 1 <= len(faces) <= MAX_FACES:
        raise ValueError('Mesh needs between 1 and 50000 faces')
    for vertex in vertices:
        if not isinstance(vertex, (list, tuple)) or len(vertex) != 3 or any(
                type(value) not in (int, float) or abs(value) > 100000 or not math.isfinite(value)
                for value in vertex):
            raise ValueError('Mesh vertices must be finite XYZ coordinates within +/-100000')
    for face in faces:
        if (not isinstance(face, (list, tuple)) or not 3 <= len(face) <= MAX_FACE_SIZE
                or any(type(index) is not int or not 0 <= index < len(vertices) for index in face)
                or len(set(face)) != len(face)):
            raise ValueError(f'Each face needs 3 to {MAX_FACE_SIZE} distinct, valid vertex indices')
    return vertices, faces
