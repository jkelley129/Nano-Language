import ast
from colorama import Fore as sty

# Supported commands and exception messages
commands = ["let", "print", "if", "elif", "else", "while"]
exceptionslist = [
    "Unknown command",
    "Invalid syntax",
    "Illegal statement",
    "Missing opening brace '{'"
]

raisedexceptions = []
exceptioncount = 0

# Block state variables
in_block = False
block_type = None  # One of 'if', 'elif', 'else', 'while'
block_lines = []
current_condition = False
executed_a_branch = False
while_condition = ""


def asteval(expr, variables):
    """
    Safely evaluate arithmetic and boolean expressions using AST,
    allowing only a limited set of operators and names (variables).
    """
    try:
        tree = ast.parse(expr, mode='eval')

        class SafeEval(ast.NodeVisitor):
            def visit_Expression(self, node):
                return self.visit(node.body)

            def visit_BinOp(self, node):
                left = self.visit(node.left)
                right = self.visit(node.right)
                ops = {
                    ast.Add: lambda: left + right,
                    ast.Sub: lambda: left - right,
                    ast.Mult: lambda: left * right,
                    ast.Div: lambda: left / right,
                    ast.Mod: lambda: left % right,
                }
                return ops.get(type(node.op), self.unsupported)()

            def visit_Compare(self, node):
                left = self.visit(node.left)
                right = self.visit(node.comparators[0])
                ops = {
                    ast.Gt: lambda: left > right,
                    ast.Lt: lambda: left < right,
                    ast.Eq: lambda: left == right,
                    ast.NotEq: lambda: left != right,
                    ast.GtE: lambda: left >= right,
                    ast.LtE: lambda: left <= right,
                }
                return ops.get(type(node.ops[0]), self.unsupported)()

            def visit_Num(self, node):  # For Python <3.8 compatibility
                return node.n

            def visit_Constant(self, node):  # For Python 3.8+
                return node.value

            def visit_Name(self, node):
                if node.id in variables:
                    return variables[node.id]
                raise NameError(f"Variable '{node.id}' is not defined")

            def visit_UnaryOp(self, node):
                operand = self.visit(node.operand)
                ops = {
                    ast.UAdd: lambda: +operand,
                    ast.USub: lambda: -operand,
                }
                return ops.get(type(node.op), self.unsupported)()

            def unsupported(self):
                raise ValueError("Unsupported operator or expression")

            def generic_visit(self, node):
                raise ValueError(f"Unsupported expression: {type(node).__name__}")

        return SafeEval().visit(tree)

    except Exception as e:
        raise ValueError(str(e))


def interpret_line(line, variables, linenum):
    """
    Parse and execute a single line of Minipy code.
    Handles block start/end and command execution.
    """
    global in_block, block_type, block_lines, current_condition
    global executed_a_branch, while_condition

    if in_block:
        # Collect block lines until closing brace
        if line == "}":
            # End of block: execute collected lines based on block type
            in_block = False
            if block_type == "while":
                # Execute while block repeatedly while condition is true
                while asteval(while_condition, variables):
                    for bline in block_lines:
                        if bline == "break":
                            return  # Break out of while loop execution
                        interpret_line(bline, variables, linenum)

            elif block_type == "else":
                if not executed_a_branch:
                    for bline in block_lines:
                        interpret_line(bline, variables, linenum)
                executed_a_branch = False

            elif block_type in ("if", "elif"):
                if current_condition and not executed_a_branch:
                    for bline in block_lines:
                        interpret_line(bline, variables, linenum)
                    executed_a_branch = True

            block_lines.clear()
            block_type = None
            return
        else:
            # Still inside a block: collect lines
            block_lines.append(line)
            return

    tokens = line.strip().split()
    if not tokens:
        return  # Skip empty lines

    keyword = tokens[0]

    if keyword == "let":
        try:
            # Expect format: let varname = expression
            parts = line.split(None, 2)
            if len(parts) < 3 or not parts[2].startswith("="):
                raiseException(exceptionslist[1], line, linenum)
                return
            name = parts[1]
            value_expr = parts[2][1:].strip()  # Remove '=' and spaces
            variables[name] = asteval(value_expr, variables)
        except Exception:
            raiseException(exceptionslist[1], line, linenum)

    elif keyword == "print":
        expr = line[6:].strip()
        try:
            print(asteval(expr, variables))
        except Exception:
            raiseException(exceptionslist[1], line, linenum)

    elif keyword in ("if", "elif"):
        try:
            condition_part = line[len(keyword):].strip()
            if not condition_part.endswith("{"):
                raiseException(exceptionslist[3], line, linenum)
                return
            condition = condition_part[:-1].strip()  # Remove trailing '{'

            in_block = True
            block_type = keyword
            current_condition = asteval(condition, variables)
        except Exception:
            raiseException(exceptionslist[1], line, linenum)

    elif keyword == "else":
        rest = line[len("else"):].strip()
        if rest != "{":
            raiseException(exceptionslist[3], line, linenum)
            return
        in_block = True
        block_type = "else"

    elif keyword == "while":
        try:
            condition_part = line[len("while"):].strip()
            if not condition_part.endswith("{"):
                raiseException(exceptionslist[3], line, linenum)
                return
            condition = condition_part[:-1].strip()

            in_block = True
            block_type = "while"
            while_condition = condition
        except Exception:
            raiseException(exceptionslist[1], line, linenum)

    elif keyword == "input":
        try:
            parts = line.split()
            if len(parts) < 2:
                raiseException(exceptionslist[1], line, linenum)
                return

            varname = parts[1]
            prompt_index = line.find("prompt")
            if prompt_index != -1:
                # Everything after the word 'prompt' is the custom prompt
                custom_prompt = line[prompt_index + len("prompt"):].strip()
            else:
                custom_prompt = ""

            user_input = input(str(custom_prompt).strip('"'))
            try:
                value = int(user_input)
            except ValueError:
                try:
                    value = float(user_input)
                except ValueError:
                    value = user_input
            variables[varname] = value

        except Exception:
            raiseException(exceptionslist[1], line, linenum)



    else:
        raiseException(exceptionslist[0], line, linenum)


def raiseException(type_, line, linenum):
    global exceptioncount
    exceptioncount += 1
    raisedexceptions.append(f"{type_}: Line {linenum+1}: {line}")


def run_minipy(code):
    variables = {}
    global in_block, block_type, block_lines, current_condition
    global executed_a_branch, while_condition, exceptioncount, raisedexceptions

    # Reset state
    in_block = False
    block_type = None
    block_lines = []
    current_condition = False
    executed_a_branch = False
    while_condition = ""
    exceptioncount = 0
    raisedexceptions.clear()

    for linenum, line in enumerate(code.splitlines()):
        interpret_line(line.strip(), variables, linenum)

    for exception in raisedexceptions:
        print(f"\n{sty.RED}{exception}{sty.RESET}")
    print(f"\n{sty.GREEN if exceptioncount == 0 else sty.RED}Exited with return code: {exceptioncount}{sty.RESET}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python nano.py <filename.nano>")
        sys.exit(1)

    filename = sys.argv[1]
    with open(filename) as f:
        run_minipy(f.read())