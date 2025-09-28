#!/usr/bin/env python3

import sys
import os
import json
import asyncio
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_complete_workflow_execution():
    """Test the complete workflow execution with fixed variable processing"""
    
    try:
        from variable_processor import process_node_variables, normalize_node_output
        
        print("🧪 Testing Complete Workflow with Fixed Variable Processing")
        print("="*70)
        
        # Simulate the user's exact workflow scenario
        print("SCENARIO: User's Workflow")
        print("- Input 0: System prompt")
        print("- Input 1: User question") 
        print("- OpenAI node uses: {{input_0.text}} and {{input_1.text}}")
        print("- Output node uses: {{openai_0.response}}")
        print()
        
        # Step 1: Simulate input node execution
        print("STEP 1: Input Node Execution")
        print("-" * 35)
        
        # Simulate what the backend creates for input nodes
        input_0_output = normalize_node_output({
            'output': 'You are a helpful AI assistant. Provide clear and concise answers.',
            'text': 'You are a helpful AI assistant. Provide clear and concise answers.',
            'type': 'Text',
            'node_name': 'input_0'
        })
        
        input_1_output = normalize_node_output({
            'output': 'What is the capital of France?',
            'text': 'What is the capital of France?',
            'type': 'Text', 
            'node_name': 'input_1'
        })
        
        # Current node outputs (simulating backend state)
        node_outputs = {
            'input_input0': input_0_output,  # Backend creates this ID
            'input_input1': input_1_output   # Backend creates this ID
        }
        
        print(f"Input Node 0 output fields: {list(input_0_output.keys())}")
        print(f"Input Node 1 output fields: {list(input_1_output.keys())}")
        print(f"Node outputs keys: {list(node_outputs.keys())}")
        print()
        
        # Step 2: Simulate OpenAI node execution
        print("STEP 2: OpenAI Node Variable Processing")
        print("-" * 40)
        
        # These are the exact prompts from user's workflow
        openai_system_template = '{{input_0.text}}'
        openai_prompt_template = '{{input_1.text}}'
        
        # Process variables
        processed_system = process_node_variables(openai_system_template, node_outputs)
        processed_prompt = process_node_variables(openai_prompt_template, node_outputs)
        
        print(f"System template: {openai_system_template}")
        print(f"Processed system: {processed_system}")
        print(f"Success: {'✅' if 'Variable processing error' not in processed_system else '❌'}")
        print()
        
        print(f"Prompt template: {openai_prompt_template}")
        print(f"Processed prompt: {processed_prompt}")
        print(f"Success: {'✅' if 'Variable processing error' not in processed_prompt else '❌'}")
        print()
        
        # Simulate OpenAI response
        if 'Variable processing error' not in processed_system and 'Variable processing error' not in processed_prompt:
            openai_response = f"The capital of France is Paris. Paris has been the capital since 987 AD and is known for its rich history, culture, and iconic landmarks like the Eiffel Tower."
            
            openai_output = normalize_node_output({
                'output': openai_response,
                'response': openai_response,
                'content': openai_response,
                'model': 'gpt-4',
                'provider': 'openai'
            })
            
            # Add OpenAI output to node outputs
            node_outputs['openai-0'] = openai_output  # Backend might create this ID
            
            print(f"OpenAI Response: {openai_response[:60]}...")
            print(f"OpenAI output fields: {list(openai_output.keys())}")
            print()
        else:
            print("❌ OpenAI execution would fail due to variable processing errors")
            return
        
        # Step 3: Simulate Output node execution
        print("STEP 3: Output Node Variable Processing")
        print("-" * 40)
        
        output_template = '{{openai_0.response}}'
        processed_output = process_node_variables(output_template, node_outputs)
        
        print(f"Output template: {output_template}")
        print(f"Processed output: {processed_output[:60]}...")
        print(f"Success: {'✅' if 'Variable processing error' not in processed_output else '❌'}")
        print()
        
        # Step 4: Final verification
        print("STEP 4: Final Verification")
        print("-" * 30)
        
        workflow_success = (
            'Variable processing error' not in processed_system and
            'Variable processing error' not in processed_prompt and  
            'Variable processing error' not in processed_output and
            processed_output == openai_response
        )
        
        print(f"System prompt substitution: {'✅' if processed_system == input_0_output['text'] else '❌'}")
        print(f"User prompt substitution: {'✅' if processed_prompt == input_1_output['text'] else '❌'}")
        print(f"Output substitution: {'✅' if processed_output == openai_response else '❌'}")
        print()
        
        # Summary
        print("="*70)
        print("🎯 WORKFLOW EXECUTION SUMMARY")
        print("="*70)
        
        if workflow_success:
            print("🎉 SUCCESS! Complete workflow execution works correctly!")
            print("✅ Variable processing is fully functional")
            print("✅ Input nodes create proper outputs")
            print("✅ OpenAI node processes variables correctly")
            print("✅ Output node displays final result")
            print()
            print("🚀 Your workflow should now work in the frontend!")
        else:
            print("❌ FAILURE! Some issues remain:")
            if 'Variable processing error' in processed_system:
                print("   - System prompt variable processing failed")
            if 'Variable processing error' in processed_prompt:
                print("   - User prompt variable processing failed")
            if 'Variable processing error' in processed_output:
                print("   - Output variable processing failed")
        
        print()
        print("📋 EXPECTED FLOW:")
        print("1. User inputs: System prompt + User question")
        print("2. OpenAI receives: Processed prompts (variables substituted)")
        print("3. OpenAI responds: AI-generated answer")
        print("4. Output shows: Final AI response")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_complete_workflow_execution()) 