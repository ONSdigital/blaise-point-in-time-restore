
def throw_error_if_empty_list(list_input: [str], argument_name: str):
    if not list_input:
        raise Exception(
            F'{argument_name} cannot be empty or none'
        )


def throw_error_if_empty_string(string_input: str, argument_name: str):
    if not string_input or not string_input.strip():
        raise Exception(
            F'{argument_name} cannot be empty or none'
        )
