#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_core_variable_processing():
    """Test just the variable processor without heavy dependencies"""
    
    print("🔍 Testing Core Variable Processing (Server Loaded Code)")
    print("="*60)
    
    try:
        # Import only the variable processor (no heavy dependencies)
        from variable_processor import process_node_variables, VariableProcessor
        
        print("✅ Successfully imported variable_processor")
        
        # Test the EXACT scenario causing the error
        print("\n📋 EXACT USER SCENARIO TEST:")
        print("Frontend sends: {{input_0.text}}, {{input_1.text}}")
        print("Backend creates: input_input0, input_input1")
        print("Question: Can our processor map input_0 -> input_input0?")
        
        # This is what the backend actually creates
        backend_node_outputs = {
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
        
        print(f"\nBackend creates these node IDs: {list(backend_node_outputs.keys())}")
        
        # Test the mapping directly
        processor = VariableProcessor()
        
        print("\n🧪 DIRECT MAPPING TESTS:")
        print("-" * 30)
        
        test_cases = [
            ('input_0', 'input_input0'),
            ('input_1', 'input_input1'),
            ('openai_0', 'openai-0'),
            ('output_0', 'output-0')
        ]
        
        for frontend_name, backend_id in test_cases:
            test_outputs = {backend_id: {'text': 'test_value', 'output': 'test_value'}}
            normalized = processor._normalize_node_name(frontend_name, test_outputs)
            
            if normalized == backend_id:
                print(f"✅ {frontend_name:<12} -> {backend_id:<15} [WORKS]")
            else:
                print(f"❌ {frontend_name:<12} -> {normalized or 'None':<15} [FAILS]")
        
        # Test full variable processing
        print("\n🎯 FULL VARIABLE PROCESSING TEST:")
        print("-" * 35)
        
        user_variables = [
            '{{input_0.text}}',
            '{{input_1.text}}',
            'System: {{input_0.text}}, User: {{input_1.text}}'
        ]
        
        for variable in user_variables:
            result = process_node_variables(variable, backend_node_outputs)
            is_working = 'Variable processing error' not in result
            status = "✅ SUCCESS" if is_working else "❌ FAILED"
            
            print(f"Variable: {variable}")
            print(f"Result:   {result}")
            print(f"Status:   [{status}]")
            print()
        
        # The critical test
        critical_test = process_node_variables('{{input_0.text}}', backend_node_outputs)
        is_critical_working = 'Variable processing error' not in critical_test
        
        print("="*60)
        print("🎯 CRITICAL RESULT:")
        
        if is_critical_working:
            print("🎉 VARIABLE PROCESSING IS FIXED!")
            print(f"✅ {{input_0.text}} correctly resolves to: '{critical_test}'")
            print("\n📝 This means the server HAS our fixes loaded.")
            print("📝 If you're still getting errors, the issue is likely:")
            print("   1. Node connections in frontend")
            print("   2. Input data not being sent properly")
            print("   3. Node IDs don't match what we tested")
        else:
            print("❌ VARIABLE PROCESSING STILL BROKEN!")
            print(f"Error: {critical_test}")
            print("\n🔧 This means:")
            print("   1. Server doesn't have our fixes, OR")
            print("   2. Server needs restart to load new code")
            print("\n💡 SOLUTION:")
            print("   1. Stop the server (Ctrl+C)")
            print("   2. Install missing dependencies:")
            print("      pip install feedparser")
            print("   3. Restart: python -m uvicorn main:app --reload --port 8000")
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print("🔧 The server likely has import issues")
        print("💡 Install missing dependencies and restart server")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_core_variable_processing() 