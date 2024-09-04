def remove_comments(string):
    database_lines = string.split('\n')
    database_lines_no_comments = ''

    for line in database_lines:
        if not line.startswith('$' or '\n'):
            database_lines_no_comments = database_lines_no_comments + line

    return database_lines_no_comments

def split_lines(string):
    return string.split('!')