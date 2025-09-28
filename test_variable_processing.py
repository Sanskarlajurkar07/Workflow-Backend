#!/usr/bin/env python3

import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_variable_processing():
    try:
        from variable_processor import process_node_variables, normalize_node_output
        
        print("🧪 Testing Variable Processing System")
        print("="*50)
        
        # Test basic variable processing
        node_outputs = {
            'input-0': {'output': 'Hello World', 'text': 'Hello World'},
            'input_1': {'output': 'System prompt', 'text': 'System prompt'},
            'openai-0': {'response': 'AI response here', 'output': 'AI response here'}
        }
        
        print(f"Available node outputs: {list(node_outputs.keys())}")
        print()
        
        # Test different variable formats
        test_cases = [
            '{{input_0.text}}',
            '{{input-0.text}}', 
            '{{input_1.output}}',
            '{{openai_0.response}}',
            '{{openai-0.response}}',
            'This is {{input_0.text}} with {{openai_0.response}}'
        ]
        
        print("Variable Processing Tests:")
        print("-" * 30)
        for case in test_cases:
            try:
                result = process_node_variables(case, node_outputs)
                print(f'{case:<40} -> {result}')
            except Exception as e:
                print(f'{case:<40} -> ERROR: {e}')
        
        print()
        
        # Test normalization
        print("Normalization Tests:")
        print("-" * 20)
        test_outputs = [
            {'response': 'Test response'},
            {'output': 'Test output'},
            {'text': 'Test text'},
            'Simple string'
        ]
        
        for test_output in test_outputs:
            try:
                normalized = normalize_node_output(test_output)
                print(f'Input: {test_output}')
                print(f'Normalized keys: {list(normalized.keys()) if isinstance(normalized, dict) else "not dict"}')
                print()
            except Exception as e:
                print(f'Input: {test_output} -> ERROR: {e}')
                print()
        
        print("✅ Variable processing tests completed!")
        
    except ImportError as e:
        print(f"❌ Failed to import variable_processor: {e}")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_variable_processing() 