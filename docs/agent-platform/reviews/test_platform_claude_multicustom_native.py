"""One native Claude + Runner + real UI encoder counterexample; loopback model."""
import asyncio
import json
from pathlib import Path
import subprocess

from agent_runner.runtime import Runtime
from agent_runner.store import RunnerError
from agent_runner.adapters.claude import ClaudeAdapter
from agent_runner.tests import test_c_native_adapters as native


class ClaudeMultiCustomNative(native.NativeAdapterTests):
    async def test_ui_multiselect_and_custom_is_answerable_through_runner(self):
        runtime = Runtime(self.workspace / "runner-state", {"claude": ClaudeAdapter})
        try:
            await runtime.set_enabled("claude", True)
            await runtime.create_session("session1", "chat1", "claude", {"kind": "managed"})
            run = await runtime.submit("session1", "chat1", "ask", "ask-fixture")
            async with asyncio.timeout(15):
                while not (pending := runtime.store.snapshot(run["run_id"])["interactions"]):
                    await asyncio.sleep(0.02)
            interaction = pending[0]
            javascript = '''
const fs=require('node:fs'),vm=require('node:vm');
global.window={};vm.runInThisContext(fs.readFileSync(process.argv[1],'utf8'));
const ui=window.ChatRawAgents.create(),data=JSON.parse(process.argv[2]);
const item={data,answers:data.questions.map(q=>({question_id:q.id,option_ids:[],text:'',custom:false}))};
for (const q of data.questions) {
 ui.selectQuestionOption(item,q,'0',true);
 if(q.type==='multi') { ui.selectQuestionCustom(item,q,true);ui.questionAnswer(item,q.id).text='Custom size'; }
}
process.stdout.write(JSON.stringify(ui.interactionReply(item)));
'''
            payload = json.loads(subprocess.check_output([
                "node", "-e", javascript, str(Path("backend/static/agents.js").resolve()), json.dumps(interaction),
            ], text=True))
            receipt = await runtime.respond(run["run_id"], interaction["interaction_id"], payload)
            corrected = json.loads(json.dumps(payload))
            for answer in corrected["answers"]:
                answer.pop("text", None)
            correction_result = "not_attempted"
            if receipt["status"] != "accepted":
                try:
                    await runtime.respond(run["run_id"], interaction["interaction_id"], corrected)
                    correction_result = "accepted"
                except RunnerError as error:
                    correction_result = f"{error.status} {error.code}"
            print(json.dumps({"native": "Claude SDK 0.2.180 / Claude Code 2.1.321", "ui_payload": payload,
                              "receipt": receipt["status"], "corrected_retry": correction_result,
                              "pending_interactions": runtime.store.snapshot(run["run_id"])["interactions"]}), flush=True)
            self.assertEqual(receipt["status"], "accepted")
            await asyncio.wait_for(runtime.tasks[run["run_id"]], 15)
            model_input = json.dumps(self.model.requests[-1][1])
            self.assertIn("Custom size", model_input)
            self.assertIn("Small", model_input)
        finally:
            await runtime.close()


for inherited_name in dir(native.NativeAdapterTests):
    if inherited_name.startswith("test_") and inherited_name not in ClaudeMultiCustomNative.__dict__:
        setattr(ClaudeMultiCustomNative, inherited_name, None)
