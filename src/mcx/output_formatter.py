import re
from typing import Dict, Any, Union

def format_dict(format_string: str, data: Dict[str, Any]) -> Any:
    """
    Converts a dict to a string output based on a format string.
    Supports wildcard (*) in brackets to return arrays.

    Args:
        format_string: String with dots (.) for dict access, brackets [] for array access,
                      and * for wildcard array operations
        data: Dictionary to extract data from

    Returns:
        String representation of the extracted value, or list if wildcard is used

    Examples:
        >>> format_dict('.content[0].id', {'content':[{'id':3}, {'id':6}]})
        '3'
        >>> format_dict('.content[*].id', {'content':[{'id':3}, {'id':6}]})
        [3, 6]
        >>> format_dict('.user.name', {'user': {'name': 'John'}})
        'John'
        >>> format_dict('.items[1][0]', {'items': [['a', 'b'], ['c', 'd']]})
        'c'
    """
    # Start with the root data
    current = data

    # Remove leading dot if present
    path = format_string.lstrip('.')

    # Split the path into tokens, handling both dots and brackets
    tokens = []
    i = 0
    current_token = ""

    while i < len(path):
        char = path[i]

        if char == '.':
            # End current token and start new one
            if current_token:
                tokens.append(current_token)
                current_token = ""
        elif char == '[':
            # End current token if exists
            if current_token:
                tokens.append(current_token)
                current_token = ""

            # Find the matching closing bracket
            bracket_count = 1
            j = i + 1
            index_content = ""

            while j < len(path) and bracket_count > 0:
                if path[j] == '[':
                    bracket_count += 1
                elif path[j] == ']':
                    bracket_count -= 1

                if bracket_count > 0:
                    index_content += path[j]
                j += 1

            # Add the index as a special token
            tokens.append(f'[{index_content}]')
            i = j - 1  # Skip to after the closing bracket
        else:
            current_token += char

        i += 1

    # Add the final token if exists
    if current_token:
        tokens.append(current_token)

    # Navigate through the data structure using tokens
    try:
        for i, token in enumerate(tokens):
            if token.startswith('[') and token.endswith(']'):
                # Array access
                index_str = token[1:-1]  # Remove brackets

                if index_str == '*':
                    # Wildcard - apply remaining path to each element
                    if not isinstance(current, list):
                        raise ValueError(f"Cannot use wildcard '*' on non-list type: {type(current)}")

                    remaining_tokens = tokens[i + 1:]
                    if not remaining_tokens:
                        # No more tokens, return the current list
                        return current

                    # Apply remaining path to each element
                    results = []
                    for item in current:
                        item_current = item
                        try:
                            # Process remaining tokens for this item
                            for remaining_token in remaining_tokens:
                                if remaining_token.startswith('[') and remaining_token.endswith(']'):
                                    remaining_index_str = remaining_token[1:-1]
                                    if remaining_index_str == '*':
                                        raise ValueError("Multiple wildcards not supported in single path")
                                    try:
                                        remaining_index = int(remaining_index_str)
                                        item_current = item_current[remaining_index]
                                    except ValueError:
                                        item_current = item_current[remaining_index_str]
                                else:
                                    # Dictionary access
                                    item_current = item_current[remaining_token]
                            results.append(item_current)
                        except (KeyError, IndexError, TypeError):
                            # Skip items that don't have the required path
                            continue

                    return results
                else:
                    # Regular array access
                    try:
                        index = int(index_str)
                        current = current[index]
                    except ValueError:
                        # Handle string indices (for dict access with bracket notation)
                        current = current[index_str]
            else:
                # Dictionary access
                current = current[token]

        return current

    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"Cannot access path '{format_string}' in provided data: {e}")

def format_dict_safe(format_string: str, data: Dict[str, Any], default: Union[str, list] = "None") -> Union[str, list]:
    """
    Safe version that returns a default value instead of raising an exception.

    Args:
        format_string: String with dots (.) for dict access, brackets [] for array access,
                      and * for wildcard array operations
        data: Dictionary to extract data from
        default: Default value to return if path is not found

    Returns:
        String representation of the extracted value, list if wildcard is used, or default
    """
    try:
        return format_dict(format_string, data)
    except ValueError:
        return default

# Test the function
if __name__ == "__main__":
    # Test cases
    test_cases = [
        # Basic examples
        ('.content[0].id', {'content': [{'id': 3}, {'id': 6}, {'id': 9}]}),
        ('.user.name', {'user': {'name': 'John', 'age': 30}}),
        ('.items[1]', {'items': ['apple', 'banana', 'cherry']}),

        # Wildcard examples
        ('.content[*].id', {'content': [{'id': 3}, {'id': 6}, {'id': 9}]}),
        ('content[*].id', {'content': [{'id': 3}, {'id': 6}, {'id': 9}]}),  # No leading dot
        ('.users[*].name', {'users': [{'name': 'Alice'}, {'name': 'Bob'}, {'name': 'Charlie'}]}),
        ('.products[*]', {'products': ['apple', 'banana', 'cherry']}),

        # Nested arrays
        ('.matrix[1][0]', {'matrix': [['a', 'b'], ['c', 'd']]}),

        # Mixed access patterns
        ('.data[0].users[1].email', {
            'data': [
                {
                    'users': [
                        {'name': 'Alice', 'email': 'alice@test.com'},
                        {'name': 'Bob', 'email': 'bob@test.com'}
                    ]
                }
            ]
        }),

        # Wildcard with nested structure
        ('.departments[*].employees[0].name', {
            'departments': [
                {'employees': [{'name': 'John'}, {'name': 'Jane'}]},
                {'employees': [{'name': 'Bob'}, {'name': 'Alice'}]}
            ]
        }),

        # Simple key access
        ('.name', {'name': 'Test'}),
    ]

    print("Testing format_dict function:")
    print("-" * 50)

    for format_str, test_data in test_cases:
        try:
            result = format_dict(format_str, test_data)
            print(f"✓ format_dict('{format_str}', ...) = '{result}'")
        except ValueError as e:
            print(f"✗ format_dict('{format_str}', ...) failed: {e}")

    # Test error cases
    print("\nTesting error cases:")
    print("-" * 30)

    error_cases = [
        ('.nonexistent', {'key': 'value'}),
        ('.content[10]', {'content': [1, 2, 3]}),
        ('.content.missing', {'content': 'string'}),
    ]

    for format_str, test_data in error_cases:
        safe_result = format_dict_safe(format_str, test_data, "NOT_FOUND")
        print(f"format_dict_safe('{format_str}', ...) = '{safe_result}'")