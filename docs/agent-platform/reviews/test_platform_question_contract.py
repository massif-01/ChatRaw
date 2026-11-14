"""Exercise the real UI answer encoder, Runner receipt ledger and Claude mapper."""

import asyncio
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from agent_runner.adapters.claude import ClaudeAdapter
from agent_runner.runtime import Runtime
from agent_runner.store import RunnerError
from agent_runner.tests.test_runtime import ControlledAdapter


class ClaudeQuestionReceiver(ControlledAdapter):
    agent_id = "claude"

    async def create_session(self, session_id, workspace, config):
        binding = await super().create_session(session_id, workspace, config)
        binding["agent_id"] = "claude"
        return binding

    async def run(self, binding, request, emit):
        self.questions = ClaudeAdapter._questions({"questions": [{
            "question": "Which sizes?", "multiSelect": True,
            "options": [{"label": "Small"}, {"label": "Large"}],
        }]})
        await emit({"type": "interaction_requested", "native_key": "native-question", "data": {
            "kind": "question", "title": "Claude needs input",
            "questions": list(self.questions.values()), "allow_cancel": True,
        }})
        self.started.set()
        await self.finish.wait()
        return {"status": "completed", "final_text": "done"}

    async def respond(self, binding, interaction_key, reply):
        # Production codec is the same function ClaudeAdapter.respond invokes
        # before resolving the SDK's pending callback.
        answer = ClaudeAdapter._answers(self.questions, reply)
        self.received.append(answer)
        self.finish.set()


class QuestionContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_ui_multiselect_plus_custom_reaches_declared_native_answer(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Runtime(directory, {"claude": ClaudeQuestionReceiver})
            try:
                await runtime.set_enabled("claude", True)
                await runtime.create_session("session1", "chat1", "claude", {"kind": "managed"})
                run = await runtime.submit("session1", "chat1", "key", "ask")
                adapter = runtime.instances["session1"]
                await adapter.started.wait()
                interaction = runtime.store.snapshot(run["run_id"])["interactions"][0]
                javascript = '''
const fs=require('node:fs'),vm=require('node:vm');
global.window={};vm.runInThisContext(fs.readFileSync(process.argv[1],'utf8'));
const ui=window.ChatRawAgents.create(), data=JSON.parse(process.argv[2]);
const item={data,answers:data.questions.map(q=>({question_id:q.id,option_ids:[],text:'',custom:false}))};
const q=data.questions[0];
ui.selectQuestionOption(item,q,'0',true);
ui.selectQuestionCustom(item,q,true);
item.answers[0].text='Custom size';
process.stdout.write(JSON.stringify(ui.interactionReply(item)));
'''
                payload = json.loads(subprocess.check_output([
                    "node", "-e", javascript, str(Path("backend/static/agents.js").resolve()), json.dumps(interaction),
                ], text=True))
                receipt = await runtime.respond(run["run_id"], interaction["interaction_id"], payload)
                correction = {"answers": [{"question_id": "0", "option_ids": ["0"]}]}
                correction_result = "not_attempted"
                if receipt["status"] != "accepted":
                    try:
                        await runtime.respond(run["run_id"], interaction["interaction_id"], correction)
                        correction_result = "accepted"
                    except RunnerError as error:
                        correction_result = f"{error.status} {error.code}"
                print(json.dumps({"ui_payload": payload, "receipt": receipt["status"],
                                  "native_answers": adapter.received, "corrected_retry": correction_result}), flush=True)
                self.assertEqual(receipt["status"], "accepted", "Declared UI answer was rejected by the native mapper and permanently consumed by Runner")
                self.assertTrue(adapter.received)
            finally:
                await runtime.close()
