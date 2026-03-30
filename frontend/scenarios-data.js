window.MPAC_SCENARIOS = [
  {
    "id": "scenario-1",
    "title": "Two AI Coding Agents Collaborate on a Microservice",
    "summary": "Intent-level assumption conflict about ID types gets resolved before code commits.",
    "assessment": "Conformant. This scenario maps cleanly to MPAC core plus governance semantics.",
    "notes": [
      "The conflict is manually reported with basis.kind = model_inference, which MPAC explicitly allows.",
      "The merged outcome keeps the backend intent alive but revised, which is consistent with RESOLUTION semantics."
    ],
    "snapshot": {
      "session_id": "sess-registration-feature",
      "clock": 10,
      "participants": {
        "human:maya": {
          "principal": {
            "principal_id": "human:maya",
            "principal_type": "human",
            "display_name": "Maya Chen",
            "roles": [
              "owner",
              "arbiter"
            ],
            "capabilities": [
              "governance.override",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": null,
          "summary": null,
          "last_seen": 1
        },
        "agent:backend-1": {
          "principal": {
            "principal_id": "agent:backend-1",
            "principal_type": "agent",
            "display_name": "Backend Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "intent.update",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": "intent-api-endpoint",
          "summary": null,
          "last_seen": 2
        },
        "agent:db-1": {
          "principal": {
            "principal_id": "agent:db-1",
            "principal_type": "agent",
            "display_name": "Database Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": "intent-db-schema",
          "summary": null,
          "last_seen": 3
        }
      },
      "intents": {
        "intent-api-endpoint": {
          "intent_id": "intent-api-endpoint",
          "principal_id": "agent:backend-1",
          "objective": "Create POST /api/v1/register endpoint with UUID-based user IDs",
          "scope": {
            "kind": "file_set",
            "resources": [
              "src/routes/auth.ts",
              "src/validators/registration.ts",
              "src/services/user-service.ts"
            ],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [],
            "extensions": {}
          },
          "assumptions": [
            "user.id is UUID",
            "bcrypt is the agreed hashing algorithm"
          ],
          "priority": "normal",
          "ttl_sec": 300,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 4,
          "updated_at_tick": 8
        },
        "intent-db-schema": {
          "intent_id": "intent-db-schema",
          "principal_id": "agent:db-1",
          "objective": "Create users table migration and add unique index on email",
          "scope": {
            "kind": "file_set",
            "resources": [
              "migrations/003_create_users.sql",
              "src/models/user.ts"
            ],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [],
            "extensions": {}
          },
          "assumptions": [
            "Using PostgreSQL 15",
            "password_hash column is VARCHAR(255) for bcrypt output",
            "user.id is UUID"
          ],
          "priority": "normal",
          "ttl_sec": 300,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 5,
          "updated_at_tick": 5
        }
      },
      "operations": {
        "op-migration": {
          "op_id": "op-migration",
          "principal_id": "agent:db-1",
          "target": "migrations/003_create_users.sql",
          "op_kind": "create",
          "intent_id": "intent-db-schema",
          "state_ref_before": "sha256:empty",
          "state_ref_after": "sha256:migration-v1",
          "change_ref": "sha256:migration-diff-001",
          "summary": "Created users table with UUID primary key.",
          "state": "COMMITTED",
          "created_at_tick": 9,
          "updated_at_tick": 9,
          "supersedes_op_id": null
        },
        "op-endpoint": {
          "op_id": "op-endpoint",
          "principal_id": "agent:backend-1",
          "target": "src/routes/auth.ts",
          "op_kind": "create",
          "intent_id": "intent-api-endpoint",
          "state_ref_before": "sha256:empty",
          "state_ref_after": "sha256:endpoint-v1",
          "change_ref": "sha256:endpoint-diff-001",
          "summary": "Created register endpoint using UUID IDs.",
          "state": "COMMITTED",
          "created_at_tick": 10,
          "updated_at_tick": 10,
          "supersedes_op_id": null
        }
      },
      "conflicts": {
        "conf-id-type": {
          "conflict_id": "conf-id-type",
          "reporter_id": "agent:db-1",
          "category": "assumption_contradiction",
          "severity": "high",
          "basis": {
            "kind": "model_inference",
            "rule_id": null
          },
          "description": "Backend agent assumes integer IDs while database schema uses UUIDs.",
          "suggested_action": "human_review",
          "related_intents": [
            "intent-api-endpoint",
            "intent-db-schema"
          ],
          "related_ops": [],
          "based_on_watermark": null,
          "state": "CLOSED"
        }
      },
      "resolutions": {
        "res-id-type": {
          "resolution_id": "res-id-type",
          "conflict_id": "conf-id-type",
          "decision": "human_override",
          "outcome": {
            "accepted": [
              "intent-db-schema"
            ],
            "rejected": [],
            "merged": [
              "intent-api-endpoint"
            ]
          },
          "rationale": "Use UUID for all entity IDs; backend updates to string-based UUID handling.",
          "resolver_id": "human:maya"
        }
      },
      "shared_state": {
        "migrations/003_create_users.sql": "sha256:migration-v1",
        "src/routes/auth.ts": "sha256:endpoint-v1"
      },
      "message_log": [
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "f00c36f5-89bc-49a7-889b-17c773476350",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "human:maya",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.418776+00:00",
          "payload": {
            "display_name": "Maya Chen",
            "roles": [
              "owner",
              "arbiter"
            ],
            "capabilities": [
              "governance.override",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 1,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "75a6f4d6-8e45-4611-86a8-2cf3a74374d9",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "agent:backend-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.418908+00:00",
          "payload": {
            "display_name": "Backend Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "intent.update",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 2,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "f0d7a876-ba7d-4901-b15f-2f821dad9c95",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "agent:db-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.418947+00:00",
          "payload": {
            "display_name": "Database Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 3,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "f4ccb24d-45f9-43dd-a524-e5401ba6acdc",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "agent:backend-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.418983+00:00",
          "payload": {
            "intent_id": "intent-api-endpoint",
            "objective": "Create POST /api/v1/register endpoint with input validation and password hashing",
            "scope": {
              "kind": "file_set",
              "resources": [
                "src/routes/auth.ts",
                "src/validators/registration.ts",
                "src/services/user-service.ts"
              ],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [],
              "extensions": {}
            },
            "assumptions": [
              "user.id is integer",
              "bcrypt is the agreed hashing algorithm",
              "Email uniqueness is enforced at the database level"
            ],
            "priority": "normal",
            "ttl_sec": 300
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 4,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "ce1877fd-1e78-42c1-a3af-dbc36cd716e9",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "agent:db-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.419033+00:00",
          "payload": {
            "intent_id": "intent-db-schema",
            "objective": "Create users table migration and add unique index on email",
            "scope": {
              "kind": "file_set",
              "resources": [
                "migrations/003_create_users.sql",
                "src/models/user.ts"
              ],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [],
              "extensions": {}
            },
            "assumptions": [
              "Using PostgreSQL 15",
              "password_hash column is VARCHAR(255) for bcrypt output",
              "user.id is UUID"
            ],
            "priority": "normal",
            "ttl_sec": 300
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 5,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "CONFLICT_REPORT",
          "message_id": "9dbe1d2d-fa3f-422d-9ed0-0a7bb9217e8e",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "agent:db-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.419079+00:00",
          "payload": {
            "conflict_id": "conf-id-type",
            "related_intents": [
              "intent-api-endpoint",
              "intent-db-schema"
            ],
            "related_ops": [],
            "category": "assumption_contradiction",
            "severity": "high",
            "basis": {
              "kind": "model_inference",
              "rule_id": null
            },
            "description": "Backend agent assumes integer IDs while database schema uses UUIDs.",
            "suggested_action": "human_review",
            "based_on_watermark": null
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 6,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "RESOLUTION",
          "message_id": "df2eea12-c8c6-48f6-9952-eee4cae7a005",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "human:maya",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.419123+00:00",
          "payload": {
            "resolution_id": "res-id-type",
            "conflict_id": "conf-id-type",
            "decision": "human_override",
            "outcome": {
              "accepted": [
                "intent-db-schema"
              ],
              "rejected": [],
              "merged": [
                "intent-api-endpoint"
              ]
            },
            "rationale": "Use UUID for all entity IDs; backend updates to string-based UUID handling."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 7,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_UPDATE",
          "message_id": "81efea4f-0031-4122-9d4f-72ee8b22249d",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "agent:backend-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.419163+00:00",
          "payload": {
            "intent_id": "intent-api-endpoint",
            "objective": "Create POST /api/v1/register endpoint with UUID-based user IDs",
            "scope": {
              "kind": "file_set",
              "resources": [
                "src/routes/auth.ts",
                "src/validators/registration.ts",
                "src/services/user-service.ts"
              ],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [],
              "extensions": {}
            },
            "assumptions": [
              "user.id is UUID",
              "bcrypt is the agreed hashing algorithm"
            ],
            "ttl_sec": 300
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 8,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "51e8881f-8d71-4326-b6cd-79021b790b71",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "agent:db-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.419205+00:00",
          "payload": {
            "op_id": "op-migration",
            "target": "migrations/003_create_users.sql",
            "op_kind": "create",
            "intent_id": "intent-db-schema",
            "state_ref_before": "sha256:empty",
            "state_ref_after": "sha256:migration-v1",
            "change_ref": "sha256:migration-diff-001",
            "summary": "Created users table with UUID primary key."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 9,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "961b83cf-da03-488b-9987-42b23b0d69b1",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "agent:backend-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.419237+00:00",
          "payload": {
            "op_id": "op-endpoint",
            "target": "src/routes/auth.ts",
            "op_kind": "create",
            "intent_id": "intent-api-endpoint",
            "state_ref_before": "sha256:empty",
            "state_ref_after": "sha256:endpoint-v1",
            "change_ref": "sha256:endpoint-diff-001",
            "summary": "Created register endpoint using UUID IDs."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 10,
            "extensions": {}
          }
        }
      ]
    }
  },
  {
    "id": "scenario-2",
    "title": "Multi-Agent Research Paper Writing with Scope Contention",
    "summary": "Two agents coordinate sequential edits on the Methods section after an owner resolution.",
    "assessment": "Conformant. The entity_set scope and merged sequential execution fit the protocol well.",
    "notes": [
      "This scenario relies on a human owner to impose ordering rather than a built-in scheduler.",
      "Both intents remain valid after resolution, which is why the outcome accepts both."
    ],
    "snapshot": {
      "session_id": "sess-paper-draft",
      "clock": 12,
      "participants": {
        "human:dr-patel": {
          "principal": {
            "principal_id": "human:dr-patel",
            "principal_type": "human",
            "display_name": "Dr. Patel",
            "roles": [
              "owner"
            ],
            "capabilities": [
              "governance.override"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": null,
          "summary": null,
          "last_seen": 1
        },
        "human:dr-liu": {
          "principal": {
            "principal_id": "human:dr-liu",
            "principal_type": "human",
            "display_name": "Dr. Liu",
            "roles": [
              "owner"
            ],
            "capabilities": [
              "governance.override"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": null,
          "summary": null,
          "last_seen": 2
        },
        "agent:writer-1": {
          "principal": {
            "principal_id": "agent:writer-1",
            "principal_type": "agent",
            "display_name": "Writer Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": "intent-methods-draft",
          "summary": null,
          "last_seen": 3
        },
        "agent:viz-1": {
          "principal": {
            "principal_id": "agent:viz-1",
            "principal_type": "agent",
            "display_name": "Viz Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": "intent-results-figures",
          "summary": null,
          "last_seen": 4
        },
        "agent:cite-1": {
          "principal": {
            "principal_id": "agent:cite-1",
            "principal_type": "agent",
            "display_name": "Citation Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": "intent-citations",
          "summary": null,
          "last_seen": 5
        }
      },
      "intents": {
        "intent-methods-draft": {
          "intent_id": "intent-methods-draft",
          "principal_id": "agent:writer-1",
          "objective": "Draft Methods section",
          "scope": {
            "kind": "entity_set",
            "resources": [],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [
              "paper.sections.methods",
              "paper.sections.methods.subsections.*"
            ],
            "extensions": {}
          },
          "assumptions": [
            "ImageNet-1K validation set",
            "Primary metric is top-1 accuracy"
          ],
          "priority": "high",
          "ttl_sec": 600,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 6,
          "updated_at_tick": 6
        },
        "intent-results-figures": {
          "intent_id": "intent-results-figures",
          "principal_id": "agent:viz-1",
          "objective": "Generate figures for Results section",
          "scope": {
            "kind": "entity_set",
            "resources": [],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [
              "paper.figures.fig1",
              "paper.figures.fig2",
              "paper.sections.results"
            ],
            "extensions": {}
          },
          "assumptions": [],
          "priority": "normal",
          "ttl_sec": 600,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 7,
          "updated_at_tick": 7
        },
        "intent-citations": {
          "intent_id": "intent-citations",
          "principal_id": "agent:cite-1",
          "objective": "Add inline citations and bibliography",
          "scope": {
            "kind": "entity_set",
            "resources": [],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [
              "paper.sections.methods",
              "paper.sections.related_work",
              "paper.bibliography"
            ],
            "extensions": {}
          },
          "assumptions": [],
          "priority": "normal",
          "ttl_sec": 600,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 8,
          "updated_at_tick": 8
        }
      },
      "operations": {
        "op-methods-text": {
          "op_id": "op-methods-text",
          "principal_id": "agent:writer-1",
          "target": "paper.sections.methods",
          "op_kind": "replace",
          "intent_id": "intent-methods-draft",
          "state_ref_before": "sha256:empty-methods",
          "state_ref_after": "sha256:methods-v1",
          "change_ref": "sha256:methods-diff-001",
          "summary": "Drafted Methods section.",
          "state": "COMMITTED",
          "created_at_tick": 11,
          "updated_at_tick": 11,
          "supersedes_op_id": null
        },
        "op-methods-citations": {
          "op_id": "op-methods-citations",
          "principal_id": "agent:cite-1",
          "target": "paper.sections.methods",
          "op_kind": "replace",
          "intent_id": "intent-citations",
          "state_ref_before": "sha256:methods-v1",
          "state_ref_after": "sha256:methods-v2-cited",
          "change_ref": "sha256:cite-diff-001",
          "summary": "Inserted citations into Methods.",
          "state": "COMMITTED",
          "created_at_tick": 12,
          "updated_at_tick": 12,
          "supersedes_op_id": null
        }
      },
      "conflicts": {
        "conf-methods-scope": {
          "conflict_id": "conf-methods-scope",
          "reporter_id": "agent:writer-1",
          "category": "scope_overlap",
          "severity": "medium",
          "basis": {
            "kind": "rule",
            "rule_id": null
          },
          "description": "Writer and citation agents both plan to modify Methods.",
          "suggested_action": "sequential_execution",
          "related_intents": [
            "intent-methods-draft",
            "intent-citations"
          ],
          "related_ops": [],
          "based_on_watermark": null,
          "state": "CLOSED"
        }
      },
      "resolutions": {
        "res-methods-scope": {
          "resolution_id": "res-methods-scope",
          "conflict_id": "conf-methods-scope",
          "decision": "merged",
          "outcome": {
            "accepted": [
              "intent-methods-draft",
              "intent-citations"
            ],
            "rejected": [],
            "merged": []
          },
          "rationale": "Writer drafts first, citation agent adds references after commit.",
          "resolver_id": "human:dr-patel"
        }
      },
      "shared_state": {
        "paper.sections.methods": "sha256:methods-v2-cited"
      },
      "message_log": [
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "84a772ff-86f2-4941-80f7-27312aadb8c2",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "human:dr-patel",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.419518+00:00",
          "payload": {
            "display_name": "Dr. Patel",
            "roles": [
              "owner"
            ],
            "capabilities": [
              "governance.override"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 1,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "513bcb2b-d942-4e92-9ff6-f0d29fc564e8",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "human:dr-liu",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.419549+00:00",
          "payload": {
            "display_name": "Dr. Liu",
            "roles": [
              "owner"
            ],
            "capabilities": [
              "governance.override"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 2,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "1415c64a-cf89-48b0-a763-17e38859852c",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:writer-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.419579+00:00",
          "payload": {
            "display_name": "Writer Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 3,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "a6686ae1-c9a7-41ba-9762-e8c08c3218c6",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:viz-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.419610+00:00",
          "payload": {
            "display_name": "Viz Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 4,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "3d0745fe-5115-4421-b965-47d6e0ed1973",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:cite-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.419639+00:00",
          "payload": {
            "display_name": "Citation Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 5,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "b02aa572-2be1-4a53-8f1c-9f78edcb1c83",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:writer-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.419670+00:00",
          "payload": {
            "intent_id": "intent-methods-draft",
            "objective": "Draft Methods section",
            "scope": {
              "kind": "entity_set",
              "resources": [],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [
                "paper.sections.methods",
                "paper.sections.methods.subsections.*"
              ],
              "extensions": {}
            },
            "assumptions": [
              "ImageNet-1K validation set",
              "Primary metric is top-1 accuracy"
            ],
            "priority": "high",
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 6,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "bf193c4a-6701-4265-875c-c6083d948583",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:viz-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.419714+00:00",
          "payload": {
            "intent_id": "intent-results-figures",
            "objective": "Generate figures for Results section",
            "scope": {
              "kind": "entity_set",
              "resources": [],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [
                "paper.figures.fig1",
                "paper.figures.fig2",
                "paper.sections.results"
              ],
              "extensions": {}
            },
            "assumptions": [],
            "priority": "normal",
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 7,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "e92d2795-5dcd-4d5f-a3e9-37bb0c173488",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:cite-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.419754+00:00",
          "payload": {
            "intent_id": "intent-citations",
            "objective": "Add inline citations and bibliography",
            "scope": {
              "kind": "entity_set",
              "resources": [],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [
                "paper.sections.methods",
                "paper.sections.related_work",
                "paper.bibliography"
              ],
              "extensions": {}
            },
            "assumptions": [],
            "priority": "normal",
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 8,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "CONFLICT_REPORT",
          "message_id": "ddb40d60-4438-4ff7-b4d1-438191517ee2",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:writer-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.419804+00:00",
          "payload": {
            "conflict_id": "conf-methods-scope",
            "related_intents": [
              "intent-methods-draft",
              "intent-citations"
            ],
            "related_ops": [],
            "category": "scope_overlap",
            "severity": "medium",
            "basis": {
              "kind": "rule",
              "rule_id": null
            },
            "description": "Writer and citation agents both plan to modify Methods.",
            "suggested_action": "sequential_execution",
            "based_on_watermark": null
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 9,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "RESOLUTION",
          "message_id": "1d037df9-6cc9-4205-9379-ff7589a44194",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "human:dr-patel",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.419843+00:00",
          "payload": {
            "resolution_id": "res-methods-scope",
            "conflict_id": "conf-methods-scope",
            "decision": "merged",
            "outcome": {
              "accepted": [
                "intent-methods-draft",
                "intent-citations"
              ],
              "rejected": [],
              "merged": []
            },
            "rationale": "Writer drafts first, citation agent adds references after commit."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 10,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "957f73d9-2b2e-4fc1-b4b4-18ebdb0bfa27",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:writer-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.419876+00:00",
          "payload": {
            "op_id": "op-methods-text",
            "target": "paper.sections.methods",
            "op_kind": "replace",
            "intent_id": "intent-methods-draft",
            "state_ref_before": "sha256:empty-methods",
            "state_ref_after": "sha256:methods-v1",
            "change_ref": "sha256:methods-diff-001",
            "summary": "Drafted Methods section."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 11,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "bdb8a217-4ac6-4ca9-8bb4-a2d35681b33e",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:cite-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.419905+00:00",
          "payload": {
            "op_id": "op-methods-citations",
            "target": "paper.sections.methods",
            "op_kind": "replace",
            "intent_id": "intent-citations",
            "state_ref_before": "sha256:methods-v1",
            "state_ref_after": "sha256:methods-v2-cited",
            "change_ref": "sha256:cite-diff-001",
            "summary": "Inserted citations into Methods."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 12,
            "extensions": {}
          }
        }
      ]
    }
  },
  {
    "id": "scenario-3",
    "title": "Production Incident Response with Escalation",
    "summary": "A speculative hotfix is proposed, rejected, and redirected during a critical incident.",
    "assessment": "Conformant. This is a strong example of CONFLICT_ESCALATE plus governance override.",
    "notes": [
      "The incident flow uses OP_PROPOSE followed by OP_REJECT, which is exactly what governance review is for.",
      "The critical conflict itself is manually inferred, not auto-detected by the reference runtime."
    ],
    "snapshot": {
      "session_id": "sess-incident-4521",
      "clock": 13,
      "participants": {
        "service:alertmanager": {
          "principal": {
            "principal_id": "service:alertmanager",
            "principal_type": "service",
            "display_name": "Alert Manager",
            "roles": [
              "observer",
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": null,
          "summary": null,
          "last_seen": 1
        },
        "human:jordan": {
          "principal": {
            "principal_id": "human:jordan",
            "principal_type": "human",
            "display_name": "Jordan",
            "roles": [
              "arbiter"
            ],
            "capabilities": [
              "governance.override",
              "op.reject"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": null,
          "summary": null,
          "last_seen": 2
        },
        "agent:diag-1": {
          "principal": {
            "principal_id": "agent:diag-1",
            "principal_type": "agent",
            "display_name": "Diagnostics Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": "intent-diagnose",
          "summary": null,
          "last_seen": 3
        },
        "agent:hotfix-1": {
          "principal": {
            "principal_id": "agent:hotfix-1",
            "principal_type": "agent",
            "display_name": "Hotfix Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.propose"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": "intent-investigate-gateway",
          "summary": null,
          "last_seen": 4
        }
      },
      "intents": {
        "intent-diagnose": {
          "intent_id": "intent-diagnose",
          "principal_id": "agent:diag-1",
          "objective": "Identify root cause of checkout failure spike",
          "scope": {
            "kind": "entity_set",
            "resources": [],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [
              "logs.checkout-service",
              "metrics.error-rate",
              "traces.checkout-flow"
            ],
            "extensions": {}
          },
          "assumptions": [
            "No deployments in the last 2 hours"
          ],
          "priority": "high",
          "ttl_sec": 180,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 5,
          "updated_at_tick": 5
        },
        "intent-hotfix-cache": {
          "intent_id": "intent-hotfix-cache",
          "principal_id": "agent:hotfix-1",
          "objective": "Flush and rebuild checkout cache",
          "scope": {
            "kind": "entity_set",
            "resources": [],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [
              "service.checkout.cache",
              "config.cache-ttl"
            ],
            "extensions": {}
          },
          "assumptions": [
            "Root cause is stale cache entries"
          ],
          "priority": "high",
          "ttl_sec": 120,
          "state": "WITHDRAWN",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 6,
          "updated_at_tick": 6
        },
        "intent-investigate-gateway": {
          "intent_id": "intent-investigate-gateway",
          "principal_id": "agent:hotfix-1",
          "objective": "Investigate payment gateway connectivity",
          "scope": {
            "kind": "entity_set",
            "resources": [],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [
              "service.payment-gateway",
              "config.payment-api-keys",
              "external.gateway-status"
            ],
            "extensions": {}
          },
          "assumptions": [
            "API keys may have rotated"
          ],
          "priority": "high",
          "ttl_sec": 180,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 13,
          "updated_at_tick": 13
        }
      },
      "operations": {
        "op-cache-flush": {
          "op_id": "op-cache-flush",
          "principal_id": "agent:hotfix-1",
          "target": "service.checkout.cache",
          "op_kind": "execute",
          "intent_id": "intent-hotfix-cache",
          "state_ref_before": null,
          "state_ref_after": null,
          "change_ref": "runbook:cache-flush-v2",
          "summary": "Flush checkout session cache and reset TTL.",
          "state": "REJECTED",
          "created_at_tick": 7,
          "updated_at_tick": 10,
          "supersedes_op_id": null
        }
      },
      "conflicts": {
        "conf-wrong-root-cause": {
          "conflict_id": "conf-wrong-root-cause",
          "reporter_id": "agent:diag-1",
          "category": "assumption_contradiction",
          "severity": "critical",
          "basis": {
            "kind": "model_inference",
            "rule_id": null
          },
          "description": "Evidence points to payment gateway 502s, not cache.",
          "suggested_action": "reject_proposed_op",
          "related_intents": [
            "intent-diagnose",
            "intent-hotfix-cache"
          ],
          "related_ops": [
            "op-cache-flush"
          ],
          "based_on_watermark": null,
          "state": "CLOSED"
        }
      },
      "resolutions": {
        "res-root-cause": {
          "resolution_id": "res-root-cause",
          "conflict_id": "conf-wrong-root-cause",
          "decision": "human_override",
          "outcome": {
            "accepted": [
              "intent-diagnose"
            ],
            "rejected": [
              "intent-hotfix-cache"
            ],
            "merged": []
          },
          "rationale": "Continue diagnosis and pivot hotfix agent to payment gateway investigation.",
          "resolver_id": "human:jordan"
        }
      },
      "shared_state": {},
      "message_log": [
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "642aab87-2449-491e-bc50-e5d4bac612e5",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "service:alertmanager",
            "principal_type": "service"
          },
          "ts": "2026-03-29T23:32:58.420223+00:00",
          "payload": {
            "display_name": "Alert Manager",
            "roles": [
              "observer",
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 1,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "8d3b36fd-a396-4eac-ba98-9483d7aa85c2",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "human:jordan",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.420255+00:00",
          "payload": {
            "display_name": "Jordan",
            "roles": [
              "arbiter"
            ],
            "capabilities": [
              "governance.override",
              "op.reject"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 2,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "1fb67574-017d-4dd7-a756-05feaf7f267c",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:diag-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.420285+00:00",
          "payload": {
            "display_name": "Diagnostics Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 3,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "bc73919d-07ed-4d42-8bd6-c3017fbb84bf",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:hotfix-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.420314+00:00",
          "payload": {
            "display_name": "Hotfix Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.propose"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 4,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "5f889f4e-182c-4569-9d11-adc483fb7ab5",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:diag-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.420354+00:00",
          "payload": {
            "intent_id": "intent-diagnose",
            "objective": "Identify root cause of checkout failure spike",
            "scope": {
              "kind": "entity_set",
              "resources": [],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [
                "logs.checkout-service",
                "metrics.error-rate",
                "traces.checkout-flow"
              ],
              "extensions": {}
            },
            "assumptions": [
              "No deployments in the last 2 hours"
            ],
            "priority": "high",
            "ttl_sec": 180
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 5,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "212b6b21-7f97-41a9-b414-23e1bdf5782c",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:hotfix-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.420396+00:00",
          "payload": {
            "intent_id": "intent-hotfix-cache",
            "objective": "Flush and rebuild checkout cache",
            "scope": {
              "kind": "entity_set",
              "resources": [],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [
                "service.checkout.cache",
                "config.cache-ttl"
              ],
              "extensions": {}
            },
            "assumptions": [
              "Root cause is stale cache entries"
            ],
            "priority": "high",
            "ttl_sec": 120
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 6,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_PROPOSE",
          "message_id": "440ae402-f800-46cd-8949-1ef1778f545e",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:hotfix-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.420435+00:00",
          "payload": {
            "op_id": "op-cache-flush",
            "target": "service.checkout.cache",
            "op_kind": "execute",
            "intent_id": "intent-hotfix-cache",
            "state_ref_before": null,
            "state_ref_after": null,
            "change_ref": "runbook:cache-flush-v2",
            "summary": "Flush checkout session cache and reset TTL."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 7,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "CONFLICT_REPORT",
          "message_id": "d85e50a9-f1cd-4277-bb70-f864d8a8228c",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:diag-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.420464+00:00",
          "payload": {
            "conflict_id": "conf-wrong-root-cause",
            "related_intents": [
              "intent-diagnose",
              "intent-hotfix-cache"
            ],
            "related_ops": [
              "op-cache-flush"
            ],
            "category": "assumption_contradiction",
            "severity": "critical",
            "basis": {
              "kind": "model_inference",
              "rule_id": null
            },
            "description": "Evidence points to payment gateway 502s, not cache.",
            "suggested_action": "reject_proposed_op",
            "based_on_watermark": null
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 8,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "CONFLICT_ESCALATE",
          "message_id": "de4b213b-5086-45bc-9839-cdf2394258c4",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:diag-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.420501+00:00",
          "payload": {
            "conflict_id": "conf-wrong-root-cause",
            "escalate_to": "human:jordan",
            "reason": "critical_severity_production_incident",
            "context": "Wrong remediation could extend outage."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 9,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_REJECT",
          "message_id": "b39b01d4-a34b-4265-9037-7a762945d712",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "human:jordan",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.420524+00:00",
          "payload": {
            "op_id": "op-cache-flush",
            "reason": "Wrong root cause. Payment gateway is returning 502s."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 10,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "RESOLUTION",
          "message_id": "7305d6e3-a665-470c-ae12-6aa0c13b28ec",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "human:jordan",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.420546+00:00",
          "payload": {
            "resolution_id": "res-root-cause",
            "conflict_id": "conf-wrong-root-cause",
            "decision": "human_override",
            "outcome": {
              "accepted": [
                "intent-diagnose"
              ],
              "rejected": [
                "intent-hotfix-cache"
              ],
              "merged": []
            },
            "rationale": "Continue diagnosis and pivot hotfix agent to payment gateway investigation."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 11,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_WITHDRAW",
          "message_id": "e4a64420-2df5-4429-b86c-9d544e277aa6",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:hotfix-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.420579+00:00",
          "payload": {
            "intent_id": "intent-hotfix-cache",
            "reason": "rejected_by_arbiter"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 12,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "0866cb36-a291-4cfd-b345-529b26b8fec7",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:hotfix-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.420600+00:00",
          "payload": {
            "intent_id": "intent-investigate-gateway",
            "objective": "Investigate payment gateway connectivity",
            "scope": {
              "kind": "entity_set",
              "resources": [],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [
                "service.payment-gateway",
                "config.payment-api-keys",
                "external.gateway-status"
              ],
              "extensions": {}
            },
            "assumptions": [
              "API keys may have rotated"
            ],
            "priority": "high",
            "ttl_sec": 180
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 13,
            "extensions": {}
          }
        }
      ]
    }
  },
  {
    "id": "scenario-4",
    "title": "Two Teams, Six Agents, One Codebase",
    "summary": "Cross-team contract ownership and later pagination mismatch are handled with structured resolutions.",
    "assessment": "Conformant, with one illustrative wrinkle: multiple RESOLUTION messages appear on the same conflict as a negotiation thread.",
    "notes": [
      "MPAC allows conflicts to stay auditable; the spec does not forbid multiple resolutions while humans negotiate.",
      "OP_SUPERSEDE is used correctly to preserve audit history when the backend route implementation changes."
    ],
    "snapshot": {
      "session_id": "sess-dashboard-feature",
      "clock": 32,
      "participants": {
        "human:alice": {
          "principal": {
            "principal_id": "human:alice",
            "principal_type": "human",
            "display_name": "Alice Wang",
            "roles": [
              "owner",
              "reviewer"
            ],
            "capabilities": [
              "governance.override",
              "conflict.report",
              "op.reject"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": null,
          "summary": null,
          "last_seen": 1
        },
        "human:bob": {
          "principal": {
            "principal_id": "human:bob",
            "principal_type": "human",
            "display_name": "Bob Martinez",
            "roles": [
              "owner",
              "reviewer"
            ],
            "capabilities": [
              "governance.override",
              "conflict.report",
              "op.reject"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": null,
          "summary": null,
          "last_seen": 2
        },
        "agent:alice-ui": {
          "principal": {
            "principal_id": "agent:alice-ui",
            "principal_type": "agent",
            "display_name": "Alice UI",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": "intent-ui-components",
          "summary": null,
          "last_seen": 3
        },
        "agent:alice-state": {
          "principal": {
            "principal_id": "agent:alice-state",
            "principal_type": "agent",
            "display_name": "Alice State",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "intent.update",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": "intent-state-management",
          "summary": null,
          "last_seen": 4
        },
        "agent:alice-test": {
          "principal": {
            "principal_id": "agent:alice-test",
            "principal_type": "agent",
            "display_name": "Alice Test",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": "intent-frontend-tests",
          "summary": null,
          "last_seen": 5
        },
        "agent:bob-api": {
          "principal": {
            "principal_id": "agent:bob-api",
            "principal_type": "agent",
            "display_name": "Bob API",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": "intent-api-endpoints",
          "summary": null,
          "last_seen": 6
        },
        "agent:bob-db": {
          "principal": {
            "principal_id": "agent:bob-db",
            "principal_type": "agent",
            "display_name": "Bob DB",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": "intent-db-tables",
          "summary": null,
          "last_seen": 7
        },
        "agent:bob-test": {
          "principal": {
            "principal_id": "agent:bob-test",
            "principal_type": "agent",
            "display_name": "Bob Test",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "offline",
          "joined": false,
          "active_intent_id": "intent-backend-tests",
          "summary": null,
          "last_seen": 32
        }
      },
      "intents": {
        "intent-db-tables": {
          "intent_id": "intent-db-tables",
          "principal_id": "agent:bob-db",
          "objective": "intent db tables",
          "scope": {
            "kind": "file_set",
            "resources": [
              "migrations/010_dashboard_tables.sql",
              "src/models/dashboard.py"
            ],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [],
            "extensions": {}
          },
          "assumptions": [],
          "priority": "normal",
          "ttl_sec": 600,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 9,
          "updated_at_tick": 9
        },
        "intent-api-endpoints": {
          "intent_id": "intent-api-endpoints",
          "principal_id": "agent:bob-api",
          "objective": "intent api endpoints",
          "scope": {
            "kind": "file_set",
            "resources": [
              "src/routes/dashboard.py",
              "src/services/dashboard_service.py",
              "api/dashboard.openapi.yaml"
            ],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [],
            "extensions": {}
          },
          "assumptions": [],
          "priority": "normal",
          "ttl_sec": 600,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 10,
          "updated_at_tick": 10
        },
        "intent-backend-tests": {
          "intent_id": "intent-backend-tests",
          "principal_id": "agent:bob-test",
          "objective": "intent backend tests",
          "scope": {
            "kind": "file_set",
            "resources": [
              "tests/integration/test_dashboard_api.py"
            ],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [],
            "extensions": {}
          },
          "assumptions": [],
          "priority": "normal",
          "ttl_sec": 600,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 11,
          "updated_at_tick": 11
        },
        "intent-ui-components": {
          "intent_id": "intent-ui-components",
          "principal_id": "agent:alice-ui",
          "objective": "intent ui components",
          "scope": {
            "kind": "file_set",
            "resources": [
              "src/components/Dashboard/DashboardGrid.tsx"
            ],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [],
            "extensions": {}
          },
          "assumptions": [],
          "priority": "normal",
          "ttl_sec": 600,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 12,
          "updated_at_tick": 12
        },
        "intent-state-management": {
          "intent_id": "intent-state-management",
          "principal_id": "agent:alice-state",
          "objective": "intent state management",
          "scope": {
            "kind": "file_set",
            "resources": [
              "src/store/dashboardSlice.ts",
              "src/hooks/useDashboard.ts",
              "api/dashboard.openapi.yaml"
            ],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [],
            "extensions": {}
          },
          "assumptions": [],
          "priority": "normal",
          "ttl_sec": 600,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 13,
          "updated_at_tick": 13
        },
        "intent-frontend-tests": {
          "intent_id": "intent-frontend-tests",
          "principal_id": "agent:alice-test",
          "objective": "intent frontend tests",
          "scope": {
            "kind": "file_set",
            "resources": [
              "src/components/Dashboard/__tests__/DashboardGrid.test.tsx"
            ],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [],
            "extensions": {}
          },
          "assumptions": [],
          "priority": "normal",
          "ttl_sec": 600,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 14,
          "updated_at_tick": 14
        }
      },
      "operations": {
        "op-db-migration": {
          "op_id": "op-db-migration",
          "principal_id": "agent:bob-db",
          "target": "migrations/010_dashboard_tables.sql",
          "op_kind": "create",
          "intent_id": "intent-db-tables",
          "state_ref_before": "sha256:empty",
          "state_ref_after": "sha256:db-mig-v1",
          "change_ref": "op-db-migration-diff",
          "summary": "op-db-migration",
          "state": "COMMITTED",
          "created_at_tick": 20,
          "updated_at_tick": 20,
          "supersedes_op_id": null
        },
        "op-api-openapi": {
          "op_id": "op-api-openapi",
          "principal_id": "agent:bob-api",
          "target": "api/dashboard.openapi.yaml",
          "op_kind": "create",
          "intent_id": "intent-api-endpoints",
          "state_ref_before": "sha256:empty",
          "state_ref_after": "sha256:openapi-v1",
          "change_ref": "op-api-openapi-diff",
          "summary": "op-api-openapi",
          "state": "COMMITTED",
          "created_at_tick": 21,
          "updated_at_tick": 21,
          "supersedes_op_id": null
        },
        "op-api-routes": {
          "op_id": "op-api-routes",
          "principal_id": "agent:bob-api",
          "target": "src/routes/dashboard.py",
          "op_kind": "create",
          "intent_id": "intent-api-endpoints",
          "state_ref_before": "sha256:empty",
          "state_ref_after": "sha256:routes-v1",
          "change_ref": "op-api-routes-diff",
          "summary": "op-api-routes",
          "state": "SUPERSEDED",
          "created_at_tick": 22,
          "updated_at_tick": 22,
          "supersedes_op_id": null
        },
        "op-ui-components": {
          "op_id": "op-ui-components",
          "principal_id": "agent:alice-ui",
          "target": "src/components/Dashboard/DashboardGrid.tsx",
          "op_kind": "create",
          "intent_id": "intent-ui-components",
          "state_ref_before": "sha256:empty",
          "state_ref_after": "sha256:grid-v1",
          "change_ref": "op-ui-components-diff",
          "summary": "op-ui-components",
          "state": "COMMITTED",
          "created_at_tick": 23,
          "updated_at_tick": 23,
          "supersedes_op_id": null
        },
        "op-state-slice": {
          "op_id": "op-state-slice",
          "principal_id": "agent:alice-state",
          "target": "src/store/dashboardSlice.ts",
          "op_kind": "create",
          "intent_id": "intent-state-management",
          "state_ref_before": "sha256:empty",
          "state_ref_after": "sha256:slice-v1",
          "change_ref": "op-state-slice-diff",
          "summary": "op-state-slice",
          "state": "COMMITTED",
          "created_at_tick": 24,
          "updated_at_tick": 24,
          "supersedes_op_id": null
        },
        "op-openapi-extensions": {
          "op_id": "op-openapi-extensions",
          "principal_id": "agent:alice-state",
          "target": "api/dashboard.openapi.yaml",
          "op_kind": "create",
          "intent_id": "intent-state-management",
          "state_ref_before": "sha256:empty",
          "state_ref_after": "sha256:openapi-v2",
          "change_ref": "op-openapi-extensions-diff",
          "summary": "op-openapi-extensions",
          "state": "COMMITTED",
          "created_at_tick": 25,
          "updated_at_tick": 25,
          "supersedes_op_id": null
        },
        "op-api-routes-v2": {
          "op_id": "op-api-routes-v2",
          "principal_id": "agent:bob-api",
          "target": "src/routes/dashboard.py",
          "op_kind": "supersede",
          "intent_id": "intent-api-endpoints",
          "state_ref_before": "sha256:routes-v1",
          "state_ref_after": "sha256:routes-v2",
          "change_ref": "sha256:routes-fix-diff-001",
          "summary": "Fixed routes to cursor pagination.",
          "state": "COMMITTED",
          "created_at_tick": 28,
          "updated_at_tick": 29,
          "supersedes_op_id": "op-api-routes"
        },
        "op-backend-tests": {
          "op_id": "op-backend-tests",
          "principal_id": "agent:bob-test",
          "target": "tests/integration/test_dashboard_api.py",
          "op_kind": "create",
          "intent_id": "intent-backend-tests",
          "state_ref_before": "sha256:empty",
          "state_ref_after": "sha256:btests-v1",
          "change_ref": "sha256:btest-diff-001",
          "summary": "Wrote backend integration tests.",
          "state": "COMMITTED",
          "created_at_tick": 30,
          "updated_at_tick": 30,
          "supersedes_op_id": null
        },
        "op-frontend-tests": {
          "op_id": "op-frontend-tests",
          "principal_id": "agent:alice-test",
          "target": "src/components/Dashboard/__tests__/DashboardGrid.test.tsx",
          "op_kind": "create",
          "intent_id": "intent-frontend-tests",
          "state_ref_before": "sha256:empty",
          "state_ref_after": "sha256:ftests-v1",
          "change_ref": "sha256:ftest-diff-001",
          "summary": "Wrote frontend tests.",
          "state": "COMMITTED",
          "created_at_tick": 31,
          "updated_at_tick": 31,
          "supersedes_op_id": null
        }
      },
      "conflicts": {
        "conf-openapi-ownership": {
          "conflict_id": "conf-openapi-ownership",
          "reporter_id": "agent:alice-state",
          "category": "scope_overlap",
          "severity": "high",
          "basis": {
            "kind": "rule",
            "rule_id": null
          },
          "description": "Both teams plan to modify api/dashboard.openapi.yaml.",
          "suggested_action": "human_review",
          "related_intents": [
            "intent-api-endpoints",
            "intent-state-management"
          ],
          "related_ops": [],
          "based_on_watermark": null,
          "state": "ACKED"
        },
        "conf-pagination-mismatch": {
          "conflict_id": "conf-pagination-mismatch",
          "reporter_id": "agent:bob-test",
          "category": "assumption_contradiction",
          "severity": "high",
          "basis": {
            "kind": "model_inference",
            "rule_id": null
          },
          "description": "Routes use offset pagination while the spec and frontend expect cursor pagination.",
          "suggested_action": "human_review",
          "related_intents": [
            "intent-api-endpoints",
            "intent-state-management"
          ],
          "related_ops": [
            "op-api-routes",
            "op-state-slice"
          ],
          "based_on_watermark": null,
          "state": "CLOSED"
        }
      },
      "resolutions": {
        "res-openapi-v1": {
          "resolution_id": "res-openapi-v1",
          "conflict_id": "conf-openapi-ownership",
          "decision": "merged",
          "outcome": {
            "accepted": [
              "intent-api-endpoints"
            ],
            "rejected": [],
            "merged": [
              "intent-state-management"
            ]
          },
          "rationale": "Bob API writes spec first; Alice state consumes it.",
          "resolver_id": "human:bob"
        },
        "res-openapi-v2": {
          "resolution_id": "res-openapi-v2",
          "conflict_id": "conf-openapi-ownership",
          "decision": "merged",
          "outcome": {
            "accepted": [
              "intent-api-endpoints",
              "intent-state-management"
            ],
            "rejected": [],
            "merged": []
          },
          "rationale": "Sequential shared writes to the OpenAPI spec are allowed.",
          "resolver_id": "human:alice"
        },
        "res-pagination": {
          "resolution_id": "res-pagination",
          "conflict_id": "conf-pagination-mismatch",
          "decision": "human_override",
          "outcome": {
            "accepted": [],
            "rejected": [],
            "merged": [
              "intent-api-endpoints",
              "intent-state-management"
            ]
          },
          "rationale": "Spec is correct; backend routes must be fixed to cursor pagination.",
          "resolver_id": "human:bob"
        }
      },
      "shared_state": {
        "migrations/010_dashboard_tables.sql": "sha256:db-mig-v1",
        "api/dashboard.openapi.yaml": "sha256:openapi-v2",
        "src/routes/dashboard.py": "sha256:routes-v2",
        "src/components/Dashboard/DashboardGrid.tsx": "sha256:grid-v1",
        "src/store/dashboardSlice.ts": "sha256:slice-v1",
        "tests/integration/test_dashboard_api.py": "sha256:btests-v1",
        "src/components/Dashboard/__tests__/DashboardGrid.test.tsx": "sha256:ftests-v1"
      },
      "message_log": [
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "784da870-4f64-41f7-8fb4-6e0e1ca67097",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "human:alice",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.420896+00:00",
          "payload": {
            "display_name": "Alice Wang",
            "roles": [
              "owner",
              "reviewer"
            ],
            "capabilities": [
              "governance.override",
              "conflict.report",
              "op.reject"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 1,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "e78ab8c8-2553-45be-8f8f-2c677aa5a1ff",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "human:bob",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.420928+00:00",
          "payload": {
            "display_name": "Bob Martinez",
            "roles": [
              "owner",
              "reviewer"
            ],
            "capabilities": [
              "governance.override",
              "conflict.report",
              "op.reject"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 2,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "7e6a30bd-258e-466d-a835-86487e5bf9f0",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-ui",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.420959+00:00",
          "payload": {
            "display_name": "Alice UI",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 3,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "e3390e56-2f5f-4fb2-87cc-e7cc58379351",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-state",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.420988+00:00",
          "payload": {
            "display_name": "Alice State",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "intent.update",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 4,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "7c5d8c7a-1810-4fd1-82d9-b322d75bb7a1",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-test",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421018+00:00",
          "payload": {
            "display_name": "Alice Test",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 5,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "8dddb21a-1e81-4013-bb93-eb6cb97061a9",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-api",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421047+00:00",
          "payload": {
            "display_name": "Bob API",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 6,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "21701b46-fdb2-4732-bcc5-080af796a90c",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-db",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421077+00:00",
          "payload": {
            "display_name": "Bob DB",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 7,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "19f87e00-ed86-40ef-a86f-bb73d9544813",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-test",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421104+00:00",
          "payload": {
            "display_name": "Bob Test",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 8,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "c70a36a3-fdad-472b-8d6e-a48ecc938aac",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-db",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421137+00:00",
          "payload": {
            "intent_id": "intent-db-tables",
            "objective": "intent db tables",
            "scope": {
              "kind": "file_set",
              "resources": [
                "migrations/010_dashboard_tables.sql",
                "src/models/dashboard.py"
              ],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [],
              "extensions": {}
            },
            "assumptions": [],
            "priority": "normal",
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 9,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "eca11aa4-2e37-4de2-a49c-1fb341ec6249",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-api",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421173+00:00",
          "payload": {
            "intent_id": "intent-api-endpoints",
            "objective": "intent api endpoints",
            "scope": {
              "kind": "file_set",
              "resources": [
                "src/routes/dashboard.py",
                "src/services/dashboard_service.py",
                "api/dashboard.openapi.yaml"
              ],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [],
              "extensions": {}
            },
            "assumptions": [],
            "priority": "normal",
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 10,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "cec6180c-b296-4d08-b159-de429fed2ac0",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-test",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421210+00:00",
          "payload": {
            "intent_id": "intent-backend-tests",
            "objective": "intent backend tests",
            "scope": {
              "kind": "file_set",
              "resources": [
                "tests/integration/test_dashboard_api.py"
              ],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [],
              "extensions": {}
            },
            "assumptions": [],
            "priority": "normal",
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 11,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "09f8b1e9-bfb4-41a0-8e90-86a63d4d5260",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-ui",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421246+00:00",
          "payload": {
            "intent_id": "intent-ui-components",
            "objective": "intent ui components",
            "scope": {
              "kind": "file_set",
              "resources": [
                "src/components/Dashboard/DashboardGrid.tsx"
              ],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [],
              "extensions": {}
            },
            "assumptions": [],
            "priority": "normal",
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 12,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "dff95642-52dc-4fa9-801e-24c247b9187e",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-state",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421281+00:00",
          "payload": {
            "intent_id": "intent-state-management",
            "objective": "intent state management",
            "scope": {
              "kind": "file_set",
              "resources": [
                "src/store/dashboardSlice.ts",
                "src/hooks/useDashboard.ts",
                "api/dashboard.openapi.yaml"
              ],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [],
              "extensions": {}
            },
            "assumptions": [],
            "priority": "normal",
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 13,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "c31afd97-3508-4bb8-9cd4-cba93e18fb07",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-test",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421317+00:00",
          "payload": {
            "intent_id": "intent-frontend-tests",
            "objective": "intent frontend tests",
            "scope": {
              "kind": "file_set",
              "resources": [
                "src/components/Dashboard/__tests__/DashboardGrid.test.tsx"
              ],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [],
              "extensions": {}
            },
            "assumptions": [],
            "priority": "normal",
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 14,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "CONFLICT_REPORT",
          "message_id": "385b5495-1835-4624-8e5e-5c826c2bb602",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-state",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421353+00:00",
          "payload": {
            "conflict_id": "conf-openapi-ownership",
            "related_intents": [
              "intent-api-endpoints",
              "intent-state-management"
            ],
            "related_ops": [],
            "category": "scope_overlap",
            "severity": "high",
            "basis": {
              "kind": "rule",
              "rule_id": null
            },
            "description": "Both teams plan to modify api/dashboard.openapi.yaml.",
            "suggested_action": "human_review",
            "based_on_watermark": null
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 15,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "RESOLUTION",
          "message_id": "ec8b0db0-bb52-4beb-87b4-565f6a20aa27",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "human:bob",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.421387+00:00",
          "payload": {
            "resolution_id": "res-openapi-v1",
            "conflict_id": "conf-openapi-ownership",
            "decision": "merged",
            "outcome": {
              "accepted": [
                "intent-api-endpoints"
              ],
              "rejected": [],
              "merged": [
                "intent-state-management"
              ]
            },
            "rationale": "Bob API writes spec first; Alice state consumes it."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 16,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "CONFLICT_ACK",
          "message_id": "c73d0652-f82e-4151-aec9-cb8d868dfc9e",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-state",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421420+00:00",
          "payload": {
            "conflict_id": "conf-openapi-ownership",
            "ack_type": "disputed"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 17,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "RESOLUTION",
          "message_id": "d370e04f-2a45-4fc5-91de-f59ae57902a5",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "human:alice",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.421442+00:00",
          "payload": {
            "resolution_id": "res-openapi-v2",
            "conflict_id": "conf-openapi-ownership",
            "decision": "merged",
            "outcome": {
              "accepted": [
                "intent-api-endpoints",
                "intent-state-management"
              ],
              "rejected": [],
              "merged": []
            },
            "rationale": "Sequential shared writes to the OpenAPI spec are allowed."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 18,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "CONFLICT_ACK",
          "message_id": "73117b10-fbbf-4d7c-8b30-998bb2901469",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "human:bob",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.421474+00:00",
          "payload": {
            "conflict_id": "conf-openapi-ownership",
            "ack_type": "accepted"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 19,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "0c15e1a8-1a94-47c0-b21e-8524e26f8179",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-db",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421496+00:00",
          "payload": {
            "op_id": "op-db-migration",
            "target": "migrations/010_dashboard_tables.sql",
            "op_kind": "create",
            "intent_id": "intent-db-tables",
            "state_ref_before": "sha256:empty",
            "state_ref_after": "sha256:db-mig-v1",
            "change_ref": "op-db-migration-diff",
            "summary": "op-db-migration"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 20,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "ae57db06-0ac6-4a6e-baf3-0eb7ef1292b2",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-api",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421524+00:00",
          "payload": {
            "op_id": "op-api-openapi",
            "target": "api/dashboard.openapi.yaml",
            "op_kind": "create",
            "intent_id": "intent-api-endpoints",
            "state_ref_before": "sha256:empty",
            "state_ref_after": "sha256:openapi-v1",
            "change_ref": "op-api-openapi-diff",
            "summary": "op-api-openapi"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 21,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "2659eafd-591f-452f-994f-453a374f2fdb",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-api",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421552+00:00",
          "payload": {
            "op_id": "op-api-routes",
            "target": "src/routes/dashboard.py",
            "op_kind": "create",
            "intent_id": "intent-api-endpoints",
            "state_ref_before": "sha256:empty",
            "state_ref_after": "sha256:routes-v1",
            "change_ref": "op-api-routes-diff",
            "summary": "op-api-routes"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 22,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "278e48d6-39f0-47d0-b3a9-1f619e06658b",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-ui",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421578+00:00",
          "payload": {
            "op_id": "op-ui-components",
            "target": "src/components/Dashboard/DashboardGrid.tsx",
            "op_kind": "create",
            "intent_id": "intent-ui-components",
            "state_ref_before": "sha256:empty",
            "state_ref_after": "sha256:grid-v1",
            "change_ref": "op-ui-components-diff",
            "summary": "op-ui-components"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 23,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "5304926c-14ed-45da-a846-2fcecba8bcb4",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-state",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421605+00:00",
          "payload": {
            "op_id": "op-state-slice",
            "target": "src/store/dashboardSlice.ts",
            "op_kind": "create",
            "intent_id": "intent-state-management",
            "state_ref_before": "sha256:empty",
            "state_ref_after": "sha256:slice-v1",
            "change_ref": "op-state-slice-diff",
            "summary": "op-state-slice"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 24,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "98bc2cb3-36b4-49d0-b8be-b28f42e9b359",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-state",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421631+00:00",
          "payload": {
            "op_id": "op-openapi-extensions",
            "target": "api/dashboard.openapi.yaml",
            "op_kind": "create",
            "intent_id": "intent-state-management",
            "state_ref_before": "sha256:empty",
            "state_ref_after": "sha256:openapi-v2",
            "change_ref": "op-openapi-extensions-diff",
            "summary": "op-openapi-extensions"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 25,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "CONFLICT_REPORT",
          "message_id": "09c63f9e-f2c6-457f-a78b-b399b9037e48",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-test",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421658+00:00",
          "payload": {
            "conflict_id": "conf-pagination-mismatch",
            "related_intents": [
              "intent-api-endpoints",
              "intent-state-management"
            ],
            "related_ops": [
              "op-api-routes",
              "op-state-slice"
            ],
            "category": "assumption_contradiction",
            "severity": "high",
            "basis": {
              "kind": "model_inference",
              "rule_id": null
            },
            "description": "Routes use offset pagination while the spec and frontend expect cursor pagination.",
            "suggested_action": "human_review",
            "based_on_watermark": null
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 26,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "RESOLUTION",
          "message_id": "ab9ecf90-cab8-4860-a1c0-d8de90180f30",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "human:bob",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.421693+00:00",
          "payload": {
            "resolution_id": "res-pagination",
            "conflict_id": "conf-pagination-mismatch",
            "decision": "human_override",
            "outcome": {
              "accepted": [],
              "rejected": [],
              "merged": [
                "intent-api-endpoints",
                "intent-state-management"
              ]
            },
            "rationale": "Spec is correct; backend routes must be fixed to cursor pagination."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 27,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_SUPERSEDE",
          "message_id": "ee1b44c5-f1eb-4ea5-8d51-4caaba807c67",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-api",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421725+00:00",
          "payload": {
            "op_id": "op-api-routes-v2",
            "supersedes_op_id": "op-api-routes",
            "intent_id": "intent-api-endpoints",
            "target": "src/routes/dashboard.py",
            "reason": "pagination_fix_per_resolution"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 28,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "be53cad8-42e4-41d3-8dbc-cde4bc58d995",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-api",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421751+00:00",
          "payload": {
            "op_id": "op-api-routes-v2",
            "target": "src/routes/dashboard.py",
            "op_kind": "replace",
            "intent_id": "intent-api-endpoints",
            "state_ref_before": "sha256:routes-v1",
            "state_ref_after": "sha256:routes-v2",
            "change_ref": "sha256:routes-fix-diff-001",
            "summary": "Fixed routes to cursor pagination."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 29,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "fa8d99c1-37db-4f6d-a717-2a06d76353f8",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-test",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421777+00:00",
          "payload": {
            "op_id": "op-backend-tests",
            "target": "tests/integration/test_dashboard_api.py",
            "op_kind": "create",
            "intent_id": "intent-backend-tests",
            "state_ref_before": "sha256:empty",
            "state_ref_after": "sha256:btests-v1",
            "change_ref": "sha256:btest-diff-001",
            "summary": "Wrote backend integration tests."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 30,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "40633c70-9b41-45dc-b64e-1b4011742def",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-test",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421804+00:00",
          "payload": {
            "op_id": "op-frontend-tests",
            "target": "src/components/Dashboard/__tests__/DashboardGrid.test.tsx",
            "op_kind": "create",
            "intent_id": "intent-frontend-tests",
            "state_ref_before": "sha256:empty",
            "state_ref_after": "sha256:ftests-v1",
            "change_ref": "sha256:ftest-diff-001",
            "summary": "Wrote frontend tests."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 31,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "GOODBYE",
          "message_id": "b4d8d635-57e9-4c10-afbf-2086f3635e46",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-test",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.421831+00:00",
          "payload": {
            "reason": "session_complete",
            "active_intents": [],
            "intent_disposition": "withdraw"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 32,
            "extensions": {}
          }
        }
      ]
    }
  },
  {
    "id": "scenario-5",
    "title": "Family of Four Plans a Vacation",
    "summary": "Family agents coordinate on schedule and budget, while parents retain final booking authority.",
    "assessment": "Conformant. This is a good non-software example of governance and resource contention.",
    "notes": [
      "The kids' agents propose bookings while the parents commit them, matching the advertised governance roles.",
      "Budget and scheduling conflicts are reported explicitly before any irreversible bookings are finalized."
    ],
    "snapshot": {
      "session_id": "sess-japan-trip-2026",
      "clock": 30,
      "participants": {
        "human:dad": {
          "principal": {
            "principal_id": "human:dad",
            "principal_type": "human",
            "display_name": "David Chen",
            "roles": [
              "owner",
              "arbiter"
            ],
            "capabilities": [
              "governance.override",
              "op.reject"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": null,
          "summary": null,
          "last_seen": 1
        },
        "human:mom": {
          "principal": {
            "principal_id": "human:mom",
            "principal_type": "human",
            "display_name": "Wei Chen",
            "roles": [
              "owner",
              "arbiter"
            ],
            "capabilities": [
              "governance.override",
              "op.reject"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": null,
          "summary": null,
          "last_seen": 2
        },
        "human:lily": {
          "principal": {
            "principal_id": "human:lily",
            "principal_type": "human",
            "display_name": "Lily Chen",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.propose",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": null,
          "summary": null,
          "last_seen": 3
        },
        "human:max": {
          "principal": {
            "principal_id": "human:max",
            "principal_type": "human",
            "display_name": "Max Chen",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.propose",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": null,
          "summary": null,
          "last_seen": 4
        },
        "agent:dad-travel": {
          "principal": {
            "principal_id": "agent:dad-travel",
            "principal_type": "agent",
            "display_name": "Dad Travel Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "intent.update",
              "op.propose",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": "intent-dad-culture",
          "summary": null,
          "last_seen": 5
        },
        "agent:mom-travel": {
          "principal": {
            "principal_id": "agent:mom-travel",
            "principal_type": "agent",
            "display_name": "Mom Travel Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "intent.update",
              "op.propose",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": "intent-mom-food",
          "summary": null,
          "last_seen": 6
        },
        "agent:lily-travel": {
          "principal": {
            "principal_id": "agent:lily-travel",
            "principal_type": "agent",
            "display_name": "Lily Travel Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "intent.update",
              "op.propose",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": "intent-lily-shopping",
          "summary": null,
          "last_seen": 7
        },
        "agent:max-travel": {
          "principal": {
            "principal_id": "agent:max-travel",
            "principal_type": "agent",
            "display_name": "Max Travel Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "intent.update",
              "op.propose",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            },
            "extensions": {}
          },
          "status": "idle",
          "joined": true,
          "active_intent_id": "intent-max-anime",
          "summary": null,
          "last_seen": 8
        }
      },
      "intents": {
        "intent-dad-culture": {
          "intent_id": "intent-dad-culture",
          "principal_id": "agent:dad-travel",
          "objective": "Updated intent-dad-culture",
          "scope": {
            "kind": "entity_set",
            "resources": [],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [
              "itinerary.day2.morning",
              "itinerary.day2.afternoon",
              "itinerary.day3.full",
              "itinerary.day6.morning",
              "budget.activities"
            ],
            "extensions": {}
          },
          "assumptions": [],
          "priority": "normal",
          "ttl_sec": 600,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 9,
          "updated_at_tick": 20
        },
        "intent-mom-food": {
          "intent_id": "intent-mom-food",
          "principal_id": "agent:mom-travel",
          "objective": "Updated intent-mom-food",
          "scope": {
            "kind": "entity_set",
            "resources": [],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [
              "itinerary.day2.lunch",
              "itinerary.day2.evening",
              "itinerary.day4.morning",
              "itinerary.day5.evening",
              "budget.dining"
            ],
            "extensions": {}
          },
          "assumptions": [],
          "priority": "normal",
          "ttl_sec": 600,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 10,
          "updated_at_tick": 21
        },
        "intent-lily-shopping": {
          "intent_id": "intent-lily-shopping",
          "principal_id": "agent:lily-travel",
          "objective": "Updated intent-lily-shopping",
          "scope": {
            "kind": "entity_set",
            "resources": [],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [
              "itinerary.day4.afternoon",
              "itinerary.day5.afternoon",
              "itinerary.day5.evening",
              "budget.shopping",
              "budget.activities"
            ],
            "extensions": {}
          },
          "assumptions": [],
          "priority": "normal",
          "ttl_sec": 600,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 11,
          "updated_at_tick": 22
        },
        "intent-max-anime": {
          "intent_id": "intent-max-anime",
          "principal_id": "agent:max-travel",
          "objective": "Updated intent-max-anime",
          "scope": {
            "kind": "entity_set",
            "resources": [],
            "pattern": null,
            "task_ids": [],
            "expression": null,
            "language": null,
            "entities": [
              "itinerary.day4.morning",
              "itinerary.day5.morning",
              "itinerary.day5.afternoon",
              "budget.shopping",
              "budget.activities"
            ],
            "extensions": {}
          },
          "assumptions": [],
          "priority": "normal",
          "ttl_sec": 600,
          "state": "ACTIVE",
          "parent_intent_id": null,
          "superseded_intent_id": null,
          "created_at_tick": 12,
          "updated_at_tick": 23
        }
      },
      "operations": {
        "op-kaiseki-reservation": {
          "op_id": "op-kaiseki-reservation",
          "principal_id": "agent:mom-travel",
          "target": "bookings.dining",
          "op_kind": "create",
          "intent_id": "intent-mom-food",
          "state_ref_before": "sha256:bookings-empty",
          "state_ref_after": "sha256:bookings-v1",
          "change_ref": "op-kaiseki-reservation",
          "summary": "op-kaiseki-reservation",
          "state": "COMMITTED",
          "created_at_tick": 24,
          "updated_at_tick": 27,
          "supersedes_op_id": null
        },
        "op-teamlab-tickets": {
          "op_id": "op-teamlab-tickets",
          "principal_id": "agent:lily-travel",
          "target": "bookings.activities",
          "op_kind": "create",
          "intent_id": "intent-lily-shopping",
          "state_ref_before": "sha256:bookings-v1",
          "state_ref_after": "sha256:bookings-v2",
          "change_ref": "op-teamlab-tickets",
          "summary": "op-teamlab-tickets",
          "state": "COMMITTED",
          "created_at_tick": 25,
          "updated_at_tick": 28,
          "supersedes_op_id": null
        },
        "op-hiroshima-tickets": {
          "op_id": "op-hiroshima-tickets",
          "principal_id": "agent:dad-travel",
          "target": "bookings.transport",
          "op_kind": "create",
          "intent_id": "intent-dad-culture",
          "state_ref_before": "sha256:bookings-v2",
          "state_ref_after": "sha256:bookings-v3",
          "change_ref": "op-hiroshima-tickets",
          "summary": "op-hiroshima-tickets",
          "state": "COMMITTED",
          "created_at_tick": 26,
          "updated_at_tick": 29,
          "supersedes_op_id": null
        },
        "op-final-itinerary": {
          "op_id": "op-final-itinerary",
          "principal_id": "agent:dad-travel",
          "target": "itinerary.final",
          "op_kind": "create",
          "intent_id": "intent-dad-culture",
          "state_ref_before": "sha256:itinerary-empty",
          "state_ref_after": "sha256:itinerary-v1",
          "change_ref": "op-final-itinerary",
          "summary": "op-final-itinerary",
          "state": "COMMITTED",
          "created_at_tick": 30,
          "updated_at_tick": 30,
          "supersedes_op_id": null
        }
      },
      "conflicts": {
        "conf-schedule-day5": {
          "conflict_id": "conf-schedule-day5",
          "reporter_id": "agent:mom-travel",
          "category": "resource_contention",
          "severity": "high",
          "basis": {
            "kind": "rule",
            "rule_id": null
          },
          "description": "Lily and Max both claimed Day 5 and Day 4 afternoon.",
          "suggested_action": "human_review",
          "related_intents": [
            "intent-lily-shopping",
            "intent-max-anime"
          ],
          "related_ops": [],
          "based_on_watermark": null,
          "state": "CLOSED"
        },
        "conf-hiroshima-vs-tokyo": {
          "conflict_id": "conf-hiroshima-vs-tokyo",
          "reporter_id": "agent:dad-travel",
          "category": "semantic_goal_conflict",
          "severity": "high",
          "basis": {
            "kind": "model_inference",
            "rule_id": null
          },
          "description": "Dad's Hiroshima trip conflicts with Lily and Max's Tokyo plans.",
          "suggested_action": "human_review",
          "related_intents": [
            "intent-dad-culture",
            "intent-lily-shopping",
            "intent-max-anime"
          ],
          "related_ops": [],
          "based_on_watermark": null,
          "state": "ACKED"
        },
        "conf-budget-overrun": {
          "conflict_id": "conf-budget-overrun",
          "reporter_id": "agent:mom-travel",
          "category": "resource_contention",
          "severity": "medium",
          "basis": {
            "kind": "heuristic",
            "rule_id": null
          },
          "description": "Combined plan exceeds the $8,000 budget.",
          "suggested_action": "human_review",
          "related_intents": [
            "intent-dad-culture",
            "intent-mom-food",
            "intent-lily-shopping",
            "intent-max-anime"
          ],
          "related_ops": [],
          "based_on_watermark": null,
          "state": "CLOSED"
        }
      },
      "resolutions": {
        "res-schedule-day5": {
          "resolution_id": "res-schedule-day5",
          "conflict_id": "conf-hiroshima-vs-tokyo",
          "decision": "merged",
          "outcome": {
            "accepted": [],
            "rejected": [],
            "merged": [
              "intent-dad-culture",
              "intent-lily-shopping",
              "intent-max-anime"
            ]
          },
          "rationale": "Move Hiroshima to Day 3 and rotate Day 5 priorities.",
          "resolver_id": "human:mom"
        },
        "res-schedule-siblings": {
          "resolution_id": "res-schedule-siblings",
          "conflict_id": "conf-schedule-day5",
          "decision": "merged",
          "outcome": {
            "accepted": [],
            "rejected": [],
            "merged": [
              "intent-lily-shopping",
              "intent-max-anime"
            ]
          },
          "rationale": "Resolved by the shared Day 4 and Day 5 restructure.",
          "resolver_id": "human:mom"
        },
        "res-budget": {
          "resolution_id": "res-budget",
          "conflict_id": "conf-budget-overrun",
          "decision": "merged",
          "outcome": {
            "accepted": [
              "intent-dad-culture",
              "intent-lily-shopping",
              "intent-max-anime"
            ],
            "rejected": [],
            "merged": [
              "intent-mom-food"
            ]
          },
          "rationale": "Drop the expensive omakase and keep the rest with a cheaper sushi dinner.",
          "resolver_id": "human:dad"
        }
      },
      "shared_state": {
        "bookings.dining": "sha256:bookings-v1",
        "bookings.activities": "sha256:bookings-v2",
        "bookings.transport": "sha256:bookings-v3",
        "itinerary.final": "sha256:itinerary-v1"
      },
      "message_log": [
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "20d2a58b-e0c8-4bbc-ba89-f01c79462900",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:dad",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.422436+00:00",
          "payload": {
            "display_name": "David Chen",
            "roles": [
              "owner",
              "arbiter"
            ],
            "capabilities": [
              "governance.override",
              "op.reject"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 1,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "b68b00c8-2ac4-4e20-9df9-094a65bdd155",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:mom",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.422466+00:00",
          "payload": {
            "display_name": "Wei Chen",
            "roles": [
              "owner",
              "arbiter"
            ],
            "capabilities": [
              "governance.override",
              "op.reject"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 2,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "f3578b42-b72a-4e9c-81b4-63ce1b82c578",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:lily",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.422495+00:00",
          "payload": {
            "display_name": "Lily Chen",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.propose",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 3,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "8c6d5d97-0665-4eb7-989d-08ff153d2baa",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:max",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.422524+00:00",
          "payload": {
            "display_name": "Max Chen",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "op.propose",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 4,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "0c3a3733-7ab6-4394-98b2-8bdfa252ce29",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:dad-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.422552+00:00",
          "payload": {
            "display_name": "Dad Travel Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "intent.update",
              "op.propose",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 5,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "c061fa4e-8d8d-420a-a732-3b7ced8d9a07",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:mom-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.422589+00:00",
          "payload": {
            "display_name": "Mom Travel Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "intent.update",
              "op.propose",
              "op.commit",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 6,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "c05355c9-5086-404e-a623-b95fc68239e1",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:lily-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.422618+00:00",
          "payload": {
            "display_name": "Lily Travel Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "intent.update",
              "op.propose",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 7,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "HELLO",
          "message_id": "63ba051a-be34-4ec8-9fab-dacabb6224b3",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:max-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.422647+00:00",
          "payload": {
            "display_name": "Max Travel Agent",
            "roles": [
              "contributor"
            ],
            "capabilities": [
              "intent.broadcast",
              "intent.update",
              "op.propose",
              "conflict.report"
            ],
            "implementation": {
              "name": "mpac-scenarios",
              "version": "0.1.0"
            }
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 8,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "e9a44826-48cd-43cb-a9e0-c2e269fbdf8f",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:dad-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.422676+00:00",
          "payload": {
            "intent_id": "intent-dad-culture",
            "objective": "intent dad culture",
            "scope": {
              "kind": "entity_set",
              "resources": [],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [
                "itinerary.day2.morning",
                "itinerary.day3.full",
                "itinerary.day5.full",
                "budget.activities"
              ],
              "extensions": {}
            },
            "assumptions": [],
            "priority": "normal",
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 9,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "21c872e6-f585-4433-ae27-eeaa8bf0aa11",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:mom-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.422720+00:00",
          "payload": {
            "intent_id": "intent-mom-food",
            "objective": "intent mom food",
            "scope": {
              "kind": "entity_set",
              "resources": [],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [
                "itinerary.day2.lunch",
                "itinerary.day3.evening",
                "itinerary.day6.evening",
                "budget.dining"
              ],
              "extensions": {}
            },
            "assumptions": [],
            "priority": "normal",
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 10,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "afd19954-b123-4e27-a074-71eeb5fc4f1a",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:lily-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.422766+00:00",
          "payload": {
            "intent_id": "intent-lily-shopping",
            "objective": "intent lily shopping",
            "scope": {
              "kind": "entity_set",
              "resources": [],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [
                "itinerary.day4.afternoon",
                "itinerary.day5.afternoon",
                "itinerary.day5.evening",
                "budget.shopping",
                "budget.activities"
              ],
              "extensions": {}
            },
            "assumptions": [],
            "priority": "normal",
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 11,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_ANNOUNCE",
          "message_id": "b19699e2-ad22-463d-82ed-75cf95774739",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:max-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.422809+00:00",
          "payload": {
            "intent_id": "intent-max-anime",
            "objective": "intent max anime",
            "scope": {
              "kind": "entity_set",
              "resources": [],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [
                "itinerary.day4.afternoon",
                "itinerary.day5.full",
                "itinerary.day6.morning",
                "budget.shopping",
                "budget.activities"
              ],
              "extensions": {}
            },
            "assumptions": [],
            "priority": "normal",
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 12,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "CONFLICT_REPORT",
          "message_id": "16bc8521-7836-48ff-a214-c06809dd5dd1",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:mom-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.422848+00:00",
          "payload": {
            "conflict_id": "conf-schedule-day5",
            "related_intents": [
              "intent-lily-shopping",
              "intent-max-anime"
            ],
            "related_ops": [],
            "category": "resource_contention",
            "severity": "high",
            "basis": {
              "kind": "rule",
              "rule_id": null
            },
            "description": "Lily and Max both claimed Day 5 and Day 4 afternoon.",
            "suggested_action": "human_review",
            "based_on_watermark": null
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 13,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "CONFLICT_REPORT",
          "message_id": "9f26d2ad-7f8d-4255-b17f-6b8bb9ca8fed",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:dad-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.422882+00:00",
          "payload": {
            "conflict_id": "conf-hiroshima-vs-tokyo",
            "related_intents": [
              "intent-dad-culture",
              "intent-lily-shopping",
              "intent-max-anime"
            ],
            "related_ops": [],
            "category": "semantic_goal_conflict",
            "severity": "high",
            "basis": {
              "kind": "model_inference",
              "rule_id": null
            },
            "description": "Dad's Hiroshima trip conflicts with Lily and Max's Tokyo plans.",
            "suggested_action": "human_review",
            "based_on_watermark": null
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 14,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "CONFLICT_REPORT",
          "message_id": "4ed04a46-b1f8-4365-b2b7-47cf154500b7",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:mom-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.422918+00:00",
          "payload": {
            "conflict_id": "conf-budget-overrun",
            "related_intents": [
              "intent-dad-culture",
              "intent-mom-food",
              "intent-lily-shopping",
              "intent-max-anime"
            ],
            "related_ops": [],
            "category": "resource_contention",
            "severity": "medium",
            "basis": {
              "kind": "heuristic",
              "rule_id": null
            },
            "description": "Combined plan exceeds the $8,000 budget.",
            "suggested_action": "human_review",
            "based_on_watermark": null
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 15,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "RESOLUTION",
          "message_id": "63366106-9216-4bf4-b7ed-2c05a2e539c1",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:mom",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.422954+00:00",
          "payload": {
            "resolution_id": "res-schedule-day5",
            "conflict_id": "conf-hiroshima-vs-tokyo",
            "decision": "merged",
            "outcome": {
              "accepted": [],
              "rejected": [],
              "merged": [
                "intent-dad-culture",
                "intent-lily-shopping",
                "intent-max-anime"
              ]
            },
            "rationale": "Move Hiroshima to Day 3 and rotate Day 5 priorities."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 16,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "CONFLICT_ACK",
          "message_id": "688b27aa-7e0c-4e13-8d4f-76cf28d2c281",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:dad",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.422986+00:00",
          "payload": {
            "conflict_id": "conf-hiroshima-vs-tokyo",
            "ack_type": "accepted"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 17,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "RESOLUTION",
          "message_id": "1e789e88-09c4-4f2b-8b28-b38eaa35ca7a",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:mom",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.423007+00:00",
          "payload": {
            "resolution_id": "res-schedule-siblings",
            "conflict_id": "conf-schedule-day5",
            "decision": "merged",
            "outcome": {
              "accepted": [],
              "rejected": [],
              "merged": [
                "intent-lily-shopping",
                "intent-max-anime"
              ]
            },
            "rationale": "Resolved by the shared Day 4 and Day 5 restructure."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 18,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "RESOLUTION",
          "message_id": "ea5fdfd9-d55c-4d83-8053-a87ab7abe8b3",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:dad",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.423038+00:00",
          "payload": {
            "resolution_id": "res-budget",
            "conflict_id": "conf-budget-overrun",
            "decision": "merged",
            "outcome": {
              "accepted": [
                "intent-dad-culture",
                "intent-lily-shopping",
                "intent-max-anime"
              ],
              "rejected": [],
              "merged": [
                "intent-mom-food"
              ]
            },
            "rationale": "Drop the expensive omakase and keep the rest with a cheaper sushi dinner."
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 19,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_UPDATE",
          "message_id": "5145b9f6-9b41-4278-9f62-217debe24c04",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:dad-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.423073+00:00",
          "payload": {
            "intent_id": "intent-dad-culture",
            "objective": "Updated intent-dad-culture",
            "scope": {
              "kind": "entity_set",
              "resources": [],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [
                "itinerary.day2.morning",
                "itinerary.day2.afternoon",
                "itinerary.day3.full",
                "itinerary.day6.morning",
                "budget.activities"
              ],
              "extensions": {}
            },
            "assumptions": null,
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 20,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_UPDATE",
          "message_id": "50c084d5-f674-4c1a-8856-2ebfaf6b2b8a",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:mom-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.423110+00:00",
          "payload": {
            "intent_id": "intent-mom-food",
            "objective": "Updated intent-mom-food",
            "scope": {
              "kind": "entity_set",
              "resources": [],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [
                "itinerary.day2.lunch",
                "itinerary.day2.evening",
                "itinerary.day4.morning",
                "itinerary.day5.evening",
                "budget.dining"
              ],
              "extensions": {}
            },
            "assumptions": null,
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 21,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_UPDATE",
          "message_id": "13e17a8a-30ed-442a-995c-99f4a5fedc51",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:lily-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.423147+00:00",
          "payload": {
            "intent_id": "intent-lily-shopping",
            "objective": "Updated intent-lily-shopping",
            "scope": {
              "kind": "entity_set",
              "resources": [],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [
                "itinerary.day4.afternoon",
                "itinerary.day5.afternoon",
                "itinerary.day5.evening",
                "budget.shopping",
                "budget.activities"
              ],
              "extensions": {}
            },
            "assumptions": null,
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 22,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "INTENT_UPDATE",
          "message_id": "dff2f02a-2fe9-415d-bb56-ca56e823c5b8",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:max-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.423182+00:00",
          "payload": {
            "intent_id": "intent-max-anime",
            "objective": "Updated intent-max-anime",
            "scope": {
              "kind": "entity_set",
              "resources": [],
              "pattern": null,
              "task_ids": [],
              "expression": null,
              "language": null,
              "entities": [
                "itinerary.day4.morning",
                "itinerary.day5.morning",
                "itinerary.day5.afternoon",
                "budget.shopping",
                "budget.activities"
              ],
              "extensions": {}
            },
            "assumptions": null,
            "ttl_sec": 600
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 23,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_PROPOSE",
          "message_id": "52f38fb9-ea51-4bca-92a2-c5ff1e1e61b7",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:mom-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.423219+00:00",
          "payload": {
            "op_id": "op-kaiseki-reservation",
            "target": "bookings.dining",
            "op_kind": "create",
            "intent_id": "intent-mom-food",
            "state_ref_before": null,
            "state_ref_after": null,
            "change_ref": "booking:kaiseki-day2",
            "summary": "op-kaiseki-reservation"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 24,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_PROPOSE",
          "message_id": "31bb532b-59a1-4d20-95df-dea07379b665",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:lily-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.423245+00:00",
          "payload": {
            "op_id": "op-teamlab-tickets",
            "target": "bookings.activities",
            "op_kind": "create",
            "intent_id": "intent-lily-shopping",
            "state_ref_before": null,
            "state_ref_after": null,
            "change_ref": "booking:teamlab-day5",
            "summary": "op-teamlab-tickets"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 25,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_PROPOSE",
          "message_id": "7fd36e86-a2c8-473a-b0e2-b55b308cb930",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:dad-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.423271+00:00",
          "payload": {
            "op_id": "op-hiroshima-tickets",
            "target": "bookings.transport",
            "op_kind": "create",
            "intent_id": "intent-dad-culture",
            "state_ref_before": null,
            "state_ref_after": null,
            "change_ref": "booking:hiroshima-day3",
            "summary": "op-hiroshima-tickets"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 26,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "269b69c9-2141-4c4f-a216-7fb1ed67f249",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:mom",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.423298+00:00",
          "payload": {
            "op_id": "op-kaiseki-reservation",
            "target": "bookings.dining",
            "op_kind": "create",
            "intent_id": "intent-mom-food",
            "state_ref_before": "sha256:bookings-empty",
            "state_ref_after": "sha256:bookings-v1",
            "change_ref": "op-kaiseki-reservation",
            "summary": "op-kaiseki-reservation"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 27,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "faf1992d-101f-433e-8809-2e4f4530c831",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:mom",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.423327+00:00",
          "payload": {
            "op_id": "op-teamlab-tickets",
            "target": "bookings.activities",
            "op_kind": "create",
            "intent_id": "intent-lily-shopping",
            "state_ref_before": "sha256:bookings-v1",
            "state_ref_after": "sha256:bookings-v2",
            "change_ref": "op-teamlab-tickets",
            "summary": "op-teamlab-tickets"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 28,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "29dd289a-6fc9-44a3-89da-aae1637aa3fb",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:dad",
            "principal_type": "human"
          },
          "ts": "2026-03-29T23:32:58.423359+00:00",
          "payload": {
            "op_id": "op-hiroshima-tickets",
            "target": "bookings.transport",
            "op_kind": "create",
            "intent_id": "intent-dad-culture",
            "state_ref_before": "sha256:bookings-v2",
            "state_ref_after": "sha256:bookings-v3",
            "change_ref": "op-hiroshima-tickets",
            "summary": "op-hiroshima-tickets"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 29,
            "extensions": {}
          }
        },
        {
          "protocol": "MPAC",
          "version": "0.1.0",
          "message_type": "OP_COMMIT",
          "message_id": "d2a1547c-f897-436c-a5bc-7b7966ed8bab",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:dad-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-29T23:32:58.423386+00:00",
          "payload": {
            "op_id": "op-final-itinerary",
            "target": "itinerary.final",
            "op_kind": "create",
            "intent_id": "intent-dad-culture",
            "state_ref_before": "sha256:itinerary-empty",
            "state_ref_after": "sha256:itinerary-v1",
            "change_ref": "op-final-itinerary",
            "summary": "op-final-itinerary"
          },
          "watermark": {
            "kind": "lamport_clock",
            "value": 30,
            "extensions": {}
          }
        }
      ]
    }
  }
];
