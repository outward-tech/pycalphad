import re
from sympy import symbols, sympify, log


class thermo_func:
    def __init__(self, function_string):
        function_line = re.compile(r'FUNCTION\s+(\w+)+\s+(\d+.\d+)?+(.*)')
        match = function_line.match(function_string)
        if match:
            self.func_name = match.group(1)
            self.start_temp = match.group(2)
            self.func_steps = match.group(3)
            self.func_temps, self.func_expressions = self._split_piecewise(self.func_steps)

    
    def _split_piecewise(self, string):
        steps = re.split(r'[;, ,Y]+', string)

        func_steps_expresions = []
        func_steps_temps = []

        for line in range(0, len(steps), 2):
            if (steps[line-1] != ('' or 'N')) and (steps[line] != ('' or 'N')) and len(steps[line]) > 0:
                func_steps_expresions.append(steps[line - 1])
                func_steps_temps.append(steps[line])

        return func_steps_temps, func_steps_expresions
    

    def _select_temp_step(self, T):
        experssions = self.func_expressions
        temperatures = self.func_temps

        for i, temperature in enumerate(temperatures):
            if T <= float(temperature):
                return(experssions[i])
                
        print('Error,  temperature above max of {}'.format(self.func_temps[-1]))


    def evaluate_function(self, temperature):
        # Define the variable
        temp = symbols('T')

        # Example string
        expression = self._select_temp_step(temperature)

        # Replace 'LN' with 'log' for natural logarithm
        expression = expression.replace('LN', 'log')

        # Convert the string to a SymPy expression
        expr = sympify(expression)

        # Substitute a value for T
        return float(expr.subs(temp, temperature).evalf())
    