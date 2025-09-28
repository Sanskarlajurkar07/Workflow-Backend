#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_variable_processing_issue():
    """Test the exact variable processing issue the user is experiencing"""
    
    try:
        from variable_processor import process_node_variables, normalize_node_output
        
        print("🧪 Testing User's Variable Processing Issue")
        print("="*60)
        
        # This is exactly what the user described
        print("USER'S SCENARIO:")
        print("- Input values: input_input0 and input_input1")
        print("- Variables in prompts: {{input_0.text}} and {{input_1.text}}")
        print("- Error: Variables not being substituted")
        print()
        
        # Simulate what the backend currently creates
        current_node_outputs = {
            'input_input0': normalize_node_output({'output': 'System prompt text', 'text': 'System prompt text'}, 'input'),
            'input_input1': normalize_node_output({'output': 'User question text', 'text': 'User question text'}, 'input')
        }
        
        # Test the exact variables from user's workflow
        user_prompts = {
            'openai_prompt': '{{input_1.text}}',
            'openai_system': '{{input_0.text}}',
            'output_template': '{{openai_0.response}}'
        }
        
        print("TESTING CURRENT BACKEND OUTPUTS:")
        print("Node Outputs:", list(current_node_outputs.keys()))
        print("Node Output Details:")
        for node_id, output in current_node_outputs.items():
            print(f"  {node_id}: {output}")
        print()
        
        print("Variable Resolution Tests:")
        print("-" * 40)
        for prompt_name, prompt_text in user_prompts.items():
            try:
                result = process_node_variables(prompt_text, current_node_outputs)
                is_error = "Variable processing error" in result
                status = "❌ FAILED" if is_error else "✅ SUCCESS"
                print(f"{prompt_name:<15}: {prompt_text:<20} -> {result} [{status}]")
            except Exception as e:
                print(f"{prompt_name:<15}: {prompt_text:<20} -> ERROR: {e} [❌ FAILED]")
        
        print()
        print("=" * 60)
        print("TESTING ENHANCED VARIABLE PROCESSOR:")
        print()
        
        comprehensive_outputs = {
            'input-0': normalize_node_output({'output': 'System prompt text', 'text': 'System prompt text'}, 'input'),
            'input-1': normalize_node_output({'output': 'User question text', 'text': 'User question text'}, 'input'),
            'openai-0': normalize_node_output({'response': 'AI generated response', 'output': 'AI generated response'}, 'openai')
        }
        
        comprehensive_tests = [
            '{{input_0.text}}',
            '{{input_1.text}}', 
            '{{openai_0.response}}',
            'Complete: {{input_0.text}} + {{input_1.text}} = {{openai_0.response}}'
        ]
        
        print("Comprehensive Outputs:")
        for node_id, output in comprehensive_outputs.items():
            print(f"  {node_id}: {output}")
        print()
        
        for test_var in comprehensive_tests:
            try:
                result = process_node_variables(test_var, comprehensive_outputs)
                is_error = "Variable processing error" in result
                status = "❌ FAILED" if is_error else "✅ SUCCESS"
                print(f"{test_var:<50} -> {result[:50]}... [{status}]")
            except Exception as e:
                print(f"{test_var:<50} -> ERROR: {e} [❌ FAILED]")
        
        print()
        print("🎯 CONCLUSION:")
        if not any("Variable processing error" in process_node_variables(test, comprehensive_outputs) 
                  for test in comprehensive_tests[:3]):
            print("🎉 Variable processing is working correctly!")
            print("🎉 The enhanced normalization fixes the issue!")
        else:
            print("⚠️  Still need to improve variable processing")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_variable_processing_issue() 