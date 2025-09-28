#!/usr/bin/env python3
"""
Simple test script for the variable system to verify it works correctly.
This script tests variable processing directly without complex node imports.
"""

import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_variable_processor():
    """Test the variable processor directly"""
    
    print("🧪 Testing Variable Processor...")
    
    try:
        from variable_processor import process_node_variables, normalize_node_output, validate_variables
        print("✅ Variable processor imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import variable processor: {e}")
        return False
    
    # Test data simulating node outputs
    node_outputs = {
        "input_0": {
            "output": "You are a helpful AI assistant. Answer questions accurately and provide detailed explanations.",
            "text": "You are a helpful AI assistant. Answer questions accurately and provide detailed explanations.",
            "content": "You are a helpful AI assistant. Answer questions accurately and provide detailed explanations."
        },
        "input_1": {
            "output": "What is the capital of France and what makes it historically significant?",
            "text": "What is the capital of France and what makes it historically significant?",
            "content": "What is the capital of France and what makes it historically significant?"
        },
        "openai_0": {
            "output": "The capital of France is Paris. Paris has been the capital since 987 AD and is known for its rich history, iconic landmarks like the Eiffel Tower and Notre-Dame Cathedral, world-class museums, and its influence on art, fashion, and cuisine.",
            "response": "The capital of France is Paris. Paris has been the capital since 987 AD and is known for its rich history, iconic landmarks like the Eiffel Tower and Notre-Dame Cathedral, world-class museums, and its influence on art, fashion, and cuisine.",
            "content": "The capital of France is Paris. Paris has been the capital since 987 AD and is known for its rich history, iconic landmarks like the Eiffel Tower and Notre-Dame Cathedral, world-class museums, and its influence on art, fashion, and cuisine."
        }
    }
    
    # Test cases matching the user's exact workflow
    test_cases = [
        {
            "name": "System prompt variable (input_0.output)",
            "template": "{{input_0.output}}",
            "expected": "You are a helpful AI assistant. Answer questions accurately and provide detailed explanations."
        },
        {
            "name": "User prompt variable (input_1.output)",
            "template": "{{input_1.output}}",
            "expected": "What is the capital of France and what makes it historically significant?"
        },
        {
            "name": "OpenAI response variable (openai_0.response)",
            "template": "{{openai_0.response}}",
            "expected": "The capital of France is Paris. Paris has been the capital since 987 AD and is known for its rich history, iconic landmarks like the Eiffel Tower and Notre-Dame Cathedral, world-class museums, and its influence on art, fashion, and cuisine."
        },
        {
            "name": "Mixed variables in output template",
            "template": "Question: {{input_1.output}}\nAnswer: {{openai_0.response}}",
            "expected": "Question: What is the capital of France and what makes it historically significant?\nAnswer: The capital of France is Paris. Paris has been the capital since 987 AD and is known for its rich history, iconic landmarks like the Eiffel Tower and Notre-Dame Cathedral, world-class museums, and its influence on art, fashion, and cuisine."
        },
        {
            "name": "Alternative field access (text fields)",
            "template": "System: {{input_0.text}} | User: {{input_1.text}}",
            "expected": "System: You are a helpful AI assistant. Answer questions accurately and provide detailed explanations. | User: What is the capital of France and what makes it historically significant?"
        }
    ]
    
    success_count = 0
    total_tests = len(test_cases)
    
    print(f"\n📋 Running {total_tests} variable resolution tests...\n")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test {i}/{total_tests}: {test_case['name']}")
        print(f"  Template: {test_case['template']}")
        
        try:
            result = process_node_variables(test_case["template"], node_outputs)
            print(f"  Result: {result[:100]}{'...' if len(result) > 100 else ''}")
            
            if result == test_case["expected"]:
                print("  ✅ PASSED")
                success_count += 1
            else:
                print("  ❌ FAILED")
                print(f"  Expected: {test_case['expected'][:100]}{'...' if len(test_case['expected']) > 100 else ''}")
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
        
        print()
    
    print(f"📊 Test Results: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("🎉 ALL TESTS PASSED! Variable system is working correctly.")
        return True
    else:
        print(f"❌ {total_tests - success_count} tests failed.")
        return False

def test_node_output_normalization():
    """Test the node output normalization"""
    
    print("\n🔧 Testing Node Output Normalization...")
    
    try:
        from variable_processor import normalize_node_output
        
        # Test input node normalization
        input_result = normalize_node_output("Hello world", "input")
        print(f"Input normalization: {input_result}")
        
        # Test AI node normalization  
        ai_result = normalize_node_output({
            "content": "AI response here",
            "model": "gpt-4"
        }, "openai")
        print(f"AI normalization: {ai_result}")
        
        # Check that expected fields exist
        required_fields = ["output", "response", "content"]
        fields_present = all(field in ai_result for field in required_fields)
        
        if fields_present:
            print("✅ Normalization working correctly")
            return True
        else:
            print("❌ Missing required fields after normalization")
            return False
            
    except Exception as e:
        print(f"❌ Normalization test failed: {e}")
        return False

def main():
    """Main test function"""
    
    print("🚀 Variable System Testing")
    print("=" * 50)
    
    # Test 1: Variable processing
    var_test_success = test_variable_processor()
    
    # Test 2: Node output normalization
    norm_test_success = test_node_output_normalization()
    
    # Final summary
    print("\n" + "=" * 50)
    print("📋 FINAL TEST SUMMARY")
    print("=" * 50)
    print(f"Variable Processing: {'✅ PASSED' if var_test_success else '❌ FAILED'}")
    print(f"Output Normalization: {'✅ PASSED' if norm_test_success else '❌ FAILED'}")
    
    if var_test_success and norm_test_success:
        print("\n🎉 ALL TESTS PASSED!")
        print("✨ Your variable system is working correctly:")
        print("   • {{input_0.output}} → System instructions")
        print("   • {{input_1.output}} → User question")  
        print("   • {{openai_0.response}} → AI response")
        print("\n🚀 Your workflow will now execute successfully with proper variable substitution!")
        return True
    else:
        print("\n❌ Some tests failed. Variable system needs attention.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 