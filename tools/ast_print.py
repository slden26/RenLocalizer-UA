import ast

code = 'text = "Hello " \\\n    "World"\n'
print(code)
t = ast.parse(code)
print(ast.dump(t, include_attributes=False, indent=2))
