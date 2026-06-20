"""Phase 5 — LMS interoperability standards (SCORM, xAPI).

Lightweight, dependency-free generators that emit valid SCORM manifests and xAPI
(Tin Can) statements from a course + its enrollments, so generated courses can be
exported into external LMSs or tracked via an LRS.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from xml.sax.saxutils import escape


def scorm_manifest(
    course_id: str, title: str, version: str = "1.2", launch: str = "index.html"
) -> str:
    """Return an IMS SCORM `imsmanifest.xml` for the course's hosted entry point."""
    schema_version = "1.2" if version == "1.2" else "2004 4th Edition"
    ident = f"COURSE-{course_id}"
    safe_title = escape(title)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="{ident}" version="1"
  xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
  xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>{schema_version}</schemaversion>
  </metadata>
  <organizations default="ORG-{course_id}">
    <organization identifier="ORG-{course_id}">
      <title>{safe_title}</title>
      <item identifier="ITEM-{course_id}" identifierref="RES-{course_id}">
        <title>{safe_title}</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="RES-{course_id}" type="webcontent"
      adlcp:scormtype="sco" href="{launch}">
      <file href="{launch}" />
    </resource>
  </resources>
</manifest>
"""


def xapi_statement(
    actor_email: str,
    actor_name: str,
    verb_id: str,
    verb_display: str,
    object_id: str,
    object_name: str,
    *,
    score_pct: int | None = None,
    success: bool | None = None,
    completed: bool | None = None,
) -> dict:
    """Build a single xAPI (Tin Can) statement."""
    stmt: dict = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "actor": {"objectType": "Agent", "name": actor_name, "mbox": f"mailto:{actor_email}"},
        "verb": {"id": verb_id, "display": {"en-US": verb_display}},
        "object": {
            "id": object_id,
            "objectType": "Activity",
            "definition": {"name": {"en-US": object_name}},
        },
    }
    result: dict = {}
    if score_pct is not None:
        result["score"] = {"scaled": round(score_pct / 100, 4), "raw": score_pct, "max": 100}
    if success is not None:
        result["success"] = success
    if completed is not None:
        result["completion"] = completed
    if result:
        stmt["result"] = result
    return stmt


# Common xAPI verbs.
VERB_COMPLETED = ("http://adlnet.gov/expapi/verbs/completed", "completed")
VERB_PROGRESSED = ("http://adlnet.gov/expapi/verbs/progressed", "progressed")
VERB_PASSED = ("http://adlnet.gov/expapi/verbs/passed", "passed")
