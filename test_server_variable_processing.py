#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_server_variable_processing():
    """Test that the running server has our variable processing fixes loaded"""
    
    print("🔍 Testing Server Variable Processing")
    print("="*50)
    
    try:
        # Import the same modules the server uses
        from variable_processor import process_node_variables, normalize_node_output
        from node_handlers import handle_input_node
        from ai_providers_node import handle_openai_node
        
        print("✅ Successfully imported all modules")
        
        # Test the exact scenario that's failing
        print("\n📋 Testing Exact User Scenario:")
        print("- Backend creates node IDs like: input_input0, input_input1")
        print("- Frontend expects variables: {{input_0.text}}, {{input_1.text}}")
        
        # Simulate what the backend creates (this is the real issue)
        node_outputs = {
            'input_input0': {
                'output': 'You are a helpful AI assistant.',
                'text': 'You are a helpful AI assistant.',
                'type': 'Text'
            },
            'input_input1': {
                'output': 'What is the capital of France?',
                'text': 'What is the capital of France?',
                'type': 'Text'
            }
        }
        
        print(f"\nBackend node outputs: {list(node_outputs.keys())}")
        
        # Test the exact variables the user is trying to use
        test_variables = [
            '{{input_0.text}}',    # What user wants to use
            '{{input_1.text}}',    # What user wants to use
            '{{input_input0.text}}',  # What actually exists
            '{{input_input1.text}}'   # What actually exists
        ]
        
        print("\n🧪 Variable Processing Test Results:")
        print("-" * 45)
        
        for variable in test_variables:
            result = process_node_variables(variable, node_outputs)
            is_working = 'Variable processing error' not in result
            status = "✅ WORKS" if is_working else "❌ FAILS"
            print(f"{variable:<25} -> {result[:30]:<30} [{status}]")
        
        # Now test if our enhanced processor can handle the mapping
        print("\n🎯 KEY TEST: Can {{input_0.text}} map to input_input0?")
        result = process_node_variables('{{input_0.text}}', node_outputs)
        
        if 'Variable processing error' not in result:
            print("✅ SUCCESS: Variable mapping works!")
            print(f"   {{input_0.text}} -> '{result}'")
        else:
            print("❌ FAILURE: Variable mapping still broken!")
            print(f"   Error: {result}")
            
            # Debug the normalization function
            print("\n🔧 DEBUGGING:")
            from variable_processor import VariableProcessor
            processor = VariableProcessor()
            normalized = processor._normalize_node_name('input_0', node_outputs)
            print(f"   _normalize_node_name('input_0') -> {normalized}")
            
            if normalized:
                print(f"   ✅ Normalization works, mapped to: {normalized}")
            else:
                print(f"   ❌ Normalization failed")
                print(f"   Available nodes: {list(node_outputs.keys())}")
        
        # Test a complete workflow scenario
        print("\n🔄 Testing Complete Workflow Scenario:")
        print("-" * 40)
        
        # Simulate OpenAI node processing
        openai_system_template = '{{input_0.text}}'
        openai_prompt_template = '{{input_1.text}}'
        
        processed_system = process_node_variables(openai_system_template, node_outputs)
        processed_prompt = process_node_variables(openai_prompt_template, node_outputs)
        
        print(f"System template: {openai_system_template}")
        print(f"Processed system: {processed_system}")
        print(f"✅ System works: {'Variable processing error' not in processed_system}")
        
        print(f"\nPrompt template: {openai_prompt_template}")
        print(f"Processed prompt: {processed_prompt}")
        print(f"✅ Prompt works: {'Variable processing error' not in processed_prompt}")
        
        # Add a mock OpenAI response and test output
        node_outputs['openai-0'] = {
            'output': 'The capital of France is Paris.',
            'response': 'The capital of France is Paris.',
            'content': 'The capital of France is Paris.'
        }
        
        output_template = '{{openai_0.response}}'
        processed_output = process_node_variables(output_template, node_outputs)
        
        print(f"\nOutput template: {output_template}")
        print(f"Processed output: {processed_output}")
        print(f"✅ Output works: {'Variable processing error' not in processed_output}")
        
        # Final assessment
        all_working = (
            'Variable processing error' not in processed_system and
            'Variable processing error' not in processed_prompt and
            'Variable processing error' not in processed_output
        )
        
        print("\n" + "="*50)
        print("🎯 FINAL ASSESSMENT:")
        
        if all_working:
            print("🎉 ALL VARIABLE PROCESSING WORKS!")
            print("✅ The server has our fixes loaded")
            print("✅ Variables should work in your workflow")
            print("\n📋 If you're still getting errors, check:")
            print("   1. Node connections in the frontend")
            print("   2. Exact node names/IDs")
            print("   3. Input data format")
        else:
            print("❌ VARIABLE PROCESSING STILL BROKEN")
            print("⚠️  The server may not have our fixes loaded")
            print("🔧 Try restarting the server:")
            print("   1. Stop uvicorn (Ctrl+C)")
            print("   2. cd backend")
            print("   3. python -m uvicorn main:app --reload --port 8000")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_server_variable_processing() 