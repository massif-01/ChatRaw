"""Validate the public interaction subset before any native response is sent."""

from datetime import datetime, timezone

from .store import RunnerError


def reject(message):
    raise RunnerError("invalid_request", message)


def object_fields(value, required, optional=()):
    if (
        not isinstance(value, dict)
        or not set(required) <= value.keys()
        or value.keys() - set(required) - set(optional)
    ):
        reject("Unexpected or missing fields")
    return value


def text(value, label, maximum=1000000, empty=False):
    if (
        not isinstance(value, str)
        or len(value) > maximum
        or (not empty and not value.strip())
    ):
        reject(f"Invalid {label}")
    return value


def expiry(value):
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError):
        reject("expires_at must be a timezone-aware ISO timestamp")


def expired(payload):
    deadline = expiry(payload.get("expires_at"))
    return deadline is not None and deadline <= datetime.now(timezone.utc)


def interaction(payload):
    kind = payload.get("kind") if isinstance(payload, dict) else None
    list_key = "questions" if kind == "question" else "decisions"
    object_fields(
        payload,
        {"kind", "title", list_key, "allow_cancel"},
        (
            {"detail", "expires_at", "presentation", "operation"}
            if kind == "approval"
            else {"detail", "expires_at", "presentation"}
        ),
    )
    if (
        kind not in ("question", "approval")
        or type(payload["allow_cancel"]) is not bool
    ):
        reject("Invalid interaction kind or cancellation flag")
    text(payload["title"], "title", 4000)
    if "detail" in payload:
        text(payload["detail"], "detail", 100000, empty=True)
    if "presentation" in payload and payload["presentation"] != "plan":
        reject("Unsupported presentation")
    expiry(payload.get("expires_at"))
    entries = payload[list_key]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 50:
        reject("Invalid interaction entries")
    identifiers = set()
    for entry in entries:
        if kind == "approval":
            object_fields(entry, {"id", "label"}, {"scope"})
            text(entry["label"], "decision label", 4000)
            if "scope" in entry:
                text(entry["scope"], "decision scope", 200)
        else:
            object_fields(
                entry, {"id", "text", "type", "options", "allow_custom", "required"}
            )
            text(entry["text"], "question text", 100000)
            if entry["type"] not in ("single", "multi", "text"):
                reject("Unsupported question type")
            if (
                type(entry["allow_custom"]) is not bool
                or type(entry["required"]) is not bool
            ):
                reject("Invalid question flags")
            options = entry["options"]
            if not isinstance(options, list) or len(options) > 200:
                reject("Invalid options")
            option_ids = set()
            for option in options:
                object_fields(option, {"id", "label"}, {"description", "recommended"})
                text(option["id"], "option ID", 200)
                text(option["label"], "option label", 4000)
                if option["id"] in option_ids:
                    reject("Duplicate option ID")
                option_ids.add(option["id"])
                if "description" in option:
                    text(option["description"], "option description", 10000, empty=True)
                if "recommended" in option and type(option["recommended"]) is not bool:
                    reject("Invalid recommended flag")
            if entry["type"] == "text" and options:
                reject("Text questions cannot declare choices")
        text(entry["id"], "entry ID", 200)
        if entry["id"] in identifiers:
            reject("Duplicate entry ID")
        identifiers.add(entry["id"])
    if "operation" in payload:
        operation = object_fields(
            payload["operation"],
            (),
            {"tool", "command", "cwd_label", "paths", "host_label"},
        )
        for key, value in operation.items():
            if key == "paths":
                if not isinstance(value, list) or len(value) > 200:
                    reject("Invalid operation paths")
                for path in value:
                    text(path, "operation path", 4000)
            else:
                text(value, key, 100000, empty=True)
    return payload


def reply(payload, response):
    if response == {"cancelled": True} and type(response["cancelled"]) is bool:
        if not payload["allow_cancel"]:
            reject("Cancellation is not allowed for this interaction")
        return response
    if payload["kind"] == "approval":
        object_fields(response, {"decision_id"})
        if response["decision_id"] not in [d["id"] for d in payload["decisions"]]:
            reject("Unknown approval decision")
    else:
        object_fields(response, {"answers"})
        answers = response["answers"]
        if not isinstance(answers, list):
            reject("answers must be a list")
        questions = {q["id"]: q for q in payload["questions"]}
        seen = set()
        for answer in answers:
            object_fields(answer, {"question_id", "option_ids"}, {"text"})
            qid = text(answer["question_id"], "question ID", 200)
            if qid not in questions or qid in seen:
                reject("Unknown or repeated question")
            seen.add(qid)
            question = questions[qid]
            options = answer["option_ids"]
            if not isinstance(options, list) or not all(
                isinstance(o, str) for o in options
            ):
                reject("Invalid selected options")
            if len(set(options)) != len(options) or set(options) - {
                o["id"] for o in question["options"]
            }:
                reject("Unknown or repeated option")
            if question["type"] == "single" and len(options) > 1:
                reject("Single-choice question has multiple answers")
            custom = answer.get("text", "")
            text(custom, "answer text", 100000, empty=True)
            if (
                "text" in answer
                and question["type"] != "text"
                and not question["allow_custom"]
            ):
                reject("Custom text is not allowed")
            if question["required"] and not options and not custom.strip():
                reject("Required question is unanswered")
        if {q["id"] for q in questions.values() if q["required"]} - seen:
            reject("Required questions are missing")
    return response
