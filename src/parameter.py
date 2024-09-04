import re
from sympy import symbols, sympify, log

class Parameter:
    def __init__(self, param_string, func_list):
        pattern = r'PARAMETER [L,G]\(([^,]+),([^;]+);([^)]*)\)\s(\d+(\.\d+)?)\s+(\S+)\s+(\S+)\s+'
        match = re.search(pattern, param_string)
        if match:
            self.phase = match.group(1)
            self.species = match.group(2).split(',')
            self.order = match.group(3)
            self.min_temp = match.group(4)
            self.expression = match.group(6)
            self.max_temp = match.group(7)
        else:
            print('Incorrect line passed into Parameter')

        self.req_functions = self._find_required_functions(func_list)

    
    def _find_required_functions(self, func_list):

        temp_req_functions = []
        for i in func_list:
            if i.func_name in self.expression:
                temp_req_functions.append(i)
        
        return temp_req_functions

    def evaluate_parameter(self, temperature):
        func_results = []
        func_names = []
        
        expression = self.expression

        for i in self.req_functions:
            func_results.append(i.evaluate_function(temperature))
            func_names.append(i.func_name)
            expression = expression.replace(str(i.func_name), str(i.evaluate_function(temperature)))

        # Define the variable
        temp = symbols('T')

        expression = expression.replace('LN', 'log')
        expression = expression.replace(';', '')

        # Convert the string to a SymPy expression
        expr = sympify(expression)

        return float(expr.subs(temp, temperature).evalf())