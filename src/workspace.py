from src.functions import thermo_func
from src.helper_functions import *

class Workspace:
    def __init__(self, string):
        self.database_string = remove_comments(string)
        self.database_lines = split_lines(self.database_string)

        self.function_list = self.parse_functions(self.database_lines)

    def parse_functions(self, lines):
        
        temp_function_list = []

        for line in lines:
            if line.startswith('FUNCTION'):
                temp_function_list.append(thermo_func(line))

        return temp_function_list