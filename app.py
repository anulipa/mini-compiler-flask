import sys
import re
from flask import Flask, request, render_template, jsonify

# --- ১. টোকেন ক্লাস ---
class Token:
    def __init__(self, type_, value=None, line=1, column=1):
        self.type = type_
        self.value = value
        self.line = line
        self.column = column

# --- ২. লেক্সার (Lexical Analyzer) ---
class Lexer:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1

    def advance(self):
        if self.pos < len(self.text):
            char = self.text[self.pos]
            if char == '\n':
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            self.pos += 1

    def get_tokens(self):
        tokens = []
        errors = []
        while self.pos < len(self.text):
            char = self.text[self.pos]

            if char.isspace():
                self.advance()
            elif char == '=':
                tokens.append(Token('ASSIGN', '=', self.line, self.column))
                self.advance()
            elif char in '+-*/':
                if tokens and tokens[-1].type in ['PLUS', 'MINUS', 'MUL', 'DIV']:
                    errors.append(f"Syntax Error: Consecutive operators '{tokens[-1].value}{char}' at Line {self.line}")
                
                types = {'+':'PLUS', '-':'MINUS', '*':'MUL', '/':'DIV'}
                tokens.append(Token(types[char], char, self.line, self.column))
                self.advance()
            elif char in '()':
                types = {'(': 'LPAREN', ')': 'RPAREN'}
                tokens.append(Token(types[char], char, self.line, self.column))
                self.advance()
            elif char == ';':
                tokens.append(Token('SEMI', ';', self.line, self.column))
                self.advance()
            elif char.isalpha():
                start_col = self.column
                start_pos = self.pos
                while self.pos < len(self.text) and (self.text[self.pos].isalnum() or self.text[self.pos] == '_'):
                    self.advance()
                word = self.text[start_pos:self.pos]
                token_type = 'PRINT' if word.upper() == 'PRINT' else 'ID'
                tokens.append(Token(token_type, word, self.line, start_col))
            elif char.isdigit():
                start_col = self.column
                start_pos = self.pos
                while self.pos < len(self.text) and self.text[self.pos].isdigit():
                    self.advance()
                tokens.append(Token('NUMBER', int(self.text[start_pos:self.pos]), self.line, start_col))
            else:
                errors.append(f"Lexical Error: Invalid character '{char}' at Line {self.line}, Col {self.column}")
                self.advance()
        
        tokens.append(Token('EOF', None, self.line, self.column))
        return tokens, errors

# --- ৩. ইন্টারপ্রিটার ---
class Interpreter:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.variables = {}
        self.errors = []

    def current_token(self):
        return self.tokens[self.pos]

    def eat(self, token_type):
        token = self.current_token()
        if token.type == token_type:
            self.pos += 1
            return token
        return None

    def execute(self):
        results = []
        while self.current_token().type != 'EOF':
            token = self.current_token()
            curr_line = token.line

            if token.type == 'ID':
                var_name = token.value
                self.pos += 1
                if not self.eat('ASSIGN'): 
                    self.errors.append(f"Syntax Error: Expected '=' after '{var_name}' at Line {curr_line}")
                
                expr_str = ""
                while self.current_token().type not in ['SEMI', 'EOF'] and self.current_token().line == curr_line:
                    t = self.current_token()
                    if t.type == 'ID':
                        if t.value in self.variables: 
                            expr_str += str(self.variables[t.value])
                        else: 
                            self.errors.append(f"Runtime Error: Variable '{t.value}' not defined at Line {t.line}")
                    elif t.type in ['NUMBER', 'PLUS', 'MINUS', 'MUL', 'DIV', 'LPAREN', 'RPAREN']:
                        expr_str += str(t.value)
                    self.pos += 1
                
                if self.current_token().type != 'SEMI':
                    self.errors.append(f"Syntax Error: Missing ';' at Line {curr_line}")
                else:
                    self.eat('SEMI')
                    try:
                        if expr_str: self.variables[var_name] = eval(expr_str)
                    except:
                        self.errors.append(f"Math Error: Invalid expression at Line {curr_line}")

            elif token.type == 'PRINT':
                self.pos += 1
                expr_str = ""
                while self.current_token().type not in ['SEMI', 'EOF'] and self.current_token().line == curr_line:
                    t = self.current_token()
                    if t.type == 'ID':
                        if t.value in self.variables: 
                            expr_str += str(self.variables[t.value])
                        else: 
                            self.errors.append(f"Runtime Error: Variable '{t.value}' not defined at Line {t.line}")
                    elif t.type in ['NUMBER', 'PLUS', 'MINUS', 'MUL', 'DIV', 'LPAREN', 'RPAREN']:
                        expr_str += str(t.value)
                    self.pos += 1
                
                if self.current_token().type != 'SEMI':
                    self.errors.append(f"Syntax Error: Missing ';' after PRINT at Line {curr_line}")
                else:
                    self.eat('SEMI')
                    try:
                        if expr_str: results.append(str(eval(expr_str)))
                    except:
                        self.errors.append(f"Math Error: Cannot evaluate PRINT at Line {curr_line}")
            else:
                self.errors.append(f"Syntax Error: Unknown command '{token.value}' at Line {curr_line}")
                self.pos += 1
                
        return results, self.errors

# --- ৪. ফ্লাস্ক সেটআপ ---
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/compile', methods=['POST'])
def handle_compile():
    data = request.json
    code = data.get('code', '')
    
    lexer = Lexer(code)
    tokens, lex_errors = lexer.get_tokens()
    
    interpreter = Interpreter(tokens)
    execution_results, exec_errors = interpreter.execute()
    
    all_errors = lex_errors + exec_errors
    
    if all_errors:
        def extract_line_number(error_msg):
            match = re.search(r'Line (\d+)', error_msg)
            return int(match.group(1)) if match else 0

        sorted_errors = sorted(all_errors, key=extract_line_number)
        return jsonify({'output': "--- ERRORS FOUND ---\n" + "\n".join(sorted_errors)})

    output = "--- EXECUTION OUTPUT ---\n"
    output += "\n".join(execution_results) if execution_results else "Execution Successful"
    return jsonify({'output': output})

if __name__ == '__main__':
    app.run(debug=True, port=5000)