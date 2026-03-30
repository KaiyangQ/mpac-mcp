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
    "presentation": {
      "tagline": "Two coding agents are building the same registration feature from different sides.",
      "shared_object": {
        "title": "Shared Work",
        "kind": "code",
        "label": "Registration flow and user identity contract",
        "before": "POST /register\n- backend assumes user.id: int\n- db schema not finalized\n- no shared contract yet",
        "after": "POST /register\n- backend uses user.id: UUID string\n- db schema uses UUID primary key\n- route and migration are compatible"
      },
      "actors": [
        {
          "name": "Backend Agent",
          "role": "Writes route and service code",
          "color": "agent-a"
        },
        {
          "name": "Database Agent",
          "role": "Designs schema and migration",
          "color": "agent-b"
        },
        {
          "name": "Maya",
          "role": "Human owner and arbiter",
          "color": "owner"
        }
      ],
      "steps": [
        {
          "title": "Both Agents Start Working",
          "focus": "shared",
          "summary": "The backend agent plans the registration endpoint while the database agent plans the user schema.",
          "left_title": "Backend Agent",
          "left_body": "I am implementing POST /register and I currently assume user IDs behave like integers in the service layer.",
          "right_title": "Database Agent",
          "right_body": "I am creating the users table and I want UUID primary keys so the system stays consistent with company standards.",
          "status": [
            "Both plans are visible before code is committed",
            "Shared feature boundary: registration"
          ],
          "protocol": [
            "INTENT_ANNOUNCE",
            "INTENT_ANNOUNCE"
          ]
        },
        {
          "title": "The Conflict Becomes Visible",
          "focus": "conflict",
          "summary": "The problem is not a merge conflict yet. It is a design mismatch: integer IDs versus UUIDs.",
          "left_title": "What Would Go Wrong",
          "left_body": "Without coordination, both agents could commit code that looks valid locally but breaks when the route and schema meet.",
          "right_title": "What MPAC Sees",
          "right_body": "The assumptions are incompatible, so the conflict is raised before incompatible code lands.",
          "status": [
            "Conflict category: assumption contradiction",
            "Severity: high"
          ],
          "protocol": [
            "CONFLICT_REPORT"
          ]
        },
        {
          "title": "Governance Decides",
          "focus": "governance",
          "summary": "Maya resolves the issue by choosing UUID as the shared contract for both agents.",
          "left_title": "Owner Decision",
          "left_body": "Use UUID everywhere. The database plan stays. The backend agent must revise its assumptions and continue.",
          "right_title": "Why This Matters",
          "right_body": "The agents do not need to guess who wins. Governance makes the decision explicit and attributable.",
          "status": [
            "Winner: UUID-based schema",
            "Backend plan stays active but must be revised"
          ],
          "protocol": [
            "RESOLUTION",
            "INTENT_UPDATE"
          ]
        },
        {
          "title": "Both Sides Commit Safely",
          "focus": "outcome",
          "summary": "The database agent commits the migration, and the backend agent commits an endpoint that now matches the schema.",
          "left_title": "Database Commit",
          "left_body": "Create users table with UUID primary key.",
          "right_title": "Backend Commit",
          "right_body": "Create register endpoint that treats user.id as a UUID string.",
          "status": [
            "No incompatible commit reached shared state",
            "Final outcome: route and schema agree"
          ],
          "protocol": [
            "OP_COMMIT",
            "OP_COMMIT"
          ]
        }
      ],
      "outcome": {
        "title": "Why MPAC Helped",
        "bullets": [
          "The agents exposed their plans before writing conflicting code.",
          "The conflict was resolved at the design layer, not after a broken integration.",
          "The final code path is compatible because the protocol forced coordination first."
        ]
      }
    },
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
          "message_id": "175e7567-ae7f-430a-a6b4-f09f6ff984ec",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "human:maya",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.983516+00:00",
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
          "message_id": "d5be14bc-89c8-457a-aafb-597dc81b8015",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "agent:backend-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.983748+00:00",
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
          "message_id": "52d9961e-f36e-43b7-ab7e-92bfa7751730",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "agent:db-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.983792+00:00",
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
          "message_id": "e7d53471-f2d9-48de-b1d7-5dcf465fde4d",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "agent:backend-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.983832+00:00",
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
          "message_id": "ea3232cc-bad4-4363-9060-cc0616814086",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "agent:db-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.983908+00:00",
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
          "message_id": "ac87a6d3-ef52-47fd-b6c3-ae21b0700c22",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "agent:db-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.983957+00:00",
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
          "message_id": "64252ffa-79be-41c3-9d09-4d29b39fc6ca",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "human:maya",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.984003+00:00",
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
          "message_id": "e6a9a76f-faa8-4998-862c-2526a5f8e414",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "agent:backend-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.984044+00:00",
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
          "message_id": "652d5663-015f-45dd-a2fd-81be49e74246",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "agent:db-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.984089+00:00",
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
          "message_id": "6fa671b1-e5b4-4e4f-b512-b1bf558143fe",
          "session_id": "sess-registration-feature",
          "sender": {
            "principal_id": "agent:backend-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.984124+00:00",
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
    "presentation": {
      "tagline": "Two writing-related agents both want to touch the Methods section of a paper.",
      "shared_object": {
        "title": "Shared Work",
        "kind": "document",
        "label": "Paper Methods section",
        "before": "Methods section is empty.\nWriter wants to draft it.\nCitation agent wants to edit it too.",
        "after": "Writer drafts Methods first.\nCitation agent adds references afterward.\nFinal section is complete and cited."
      },
      "actors": [
        {
          "name": "Writer Agent",
          "role": "Drafts section text",
          "color": "agent-a"
        },
        {
          "name": "Citation Agent",
          "role": "Adds references",
          "color": "agent-b"
        },
        {
          "name": "Dr. Patel",
          "role": "Section owner",
          "color": "owner"
        }
      ],
      "steps": [
        {
          "title": "Both Agents Aim at the Same Section",
          "focus": "shared",
          "summary": "The writer wants to draft Methods and the citation agent wants to edit Methods too.",
          "left_title": "Writer Agent",
          "left_body": "I want to produce the full Methods narrative.",
          "right_title": "Citation Agent",
          "right_body": "I want to insert references into Methods and update the bibliography.",
          "status": [
            "Shared section: Methods",
            "Risk: concurrent edits"
          ],
          "protocol": [
            "INTENT_ANNOUNCE",
            "INTENT_ANNOUNCE"
          ]
        },
        {
          "title": "MPAC Turns Overlap into an Explicit Conflict",
          "focus": "conflict",
          "summary": "Instead of quietly racing to edit the same section, the overlap becomes visible.",
          "left_title": "The Real Problem",
          "left_body": "If both agents edit Methods at once, one can easily overwrite the other's paragraphs.",
          "right_title": "Protocol Effect",
          "right_body": "The overlap is elevated into a conflict report so someone can decide execution order.",
          "status": [
            "Conflict category: scope overlap",
            "Suggested action: sequential execution"
          ],
          "protocol": [
            "CONFLICT_REPORT"
          ]
        },
        {
          "title": "The Owner Chooses a Safe Sequence",
          "focus": "governance",
          "summary": "Dr. Patel allows both agents to continue, but only in order.",
          "left_title": "Resolution",
          "left_body": "Writer drafts first. Citation agent waits until the text exists, then edits the updated version.",
          "right_title": "Result",
          "right_body": "No one loses ownership of the work. They just stop colliding.",
          "status": [
            "Both intents accepted",
            "Execution order is explicit"
          ],
          "protocol": [
            "RESOLUTION"
          ]
        },
        {
          "title": "The Paper Improves in Two Passes",
          "focus": "outcome",
          "summary": "The writer commits the Methods text, then the citation agent safely enriches the finished section.",
          "left_title": "Pass 1",
          "left_body": "Methods draft is written.",
          "right_title": "Pass 2",
          "right_body": "Citations are inserted into the exact text that now exists.",
          "status": [
            "Final section is ordered and complete",
            "No accidental overwrite"
          ],
          "protocol": [
            "OP_COMMIT",
            "OP_COMMIT"
          ]
        }
      ],
      "outcome": {
        "title": "Why MPAC Helped",
        "bullets": [
          "The overlap was surfaced before simultaneous edits damaged the paper.",
          "Governance added ordering without requiring a custom scheduler.",
          "The final document kept contributions from both agents."
        ]
      }
    },
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
          "message_id": "75b6f472-0ccc-40cf-b498-7b5b8441580f",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "human:dr-patel",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.984400+00:00",
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
          "message_id": "c3d46660-73c7-4c94-95f3-46db26ffdf20",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "human:dr-liu",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.984433+00:00",
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
          "message_id": "ef9d0b1c-16fd-44a5-934e-a227bb587706",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:writer-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.984464+00:00",
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
          "message_id": "cdef3043-f70d-4237-8761-1743bc8125c2",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:viz-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.984497+00:00",
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
          "message_id": "e15e390b-5a51-4c9a-96d9-ffa1ccb1e768",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:cite-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.984529+00:00",
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
          "message_id": "e47eed4a-8e08-4b13-85e9-b33a852f75d4",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:writer-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.984562+00:00",
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
          "message_id": "6a3b8fcb-8a0d-49c1-9f52-4fc087b8303d",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:viz-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.984606+00:00",
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
          "message_id": "47ce17bc-3c64-4153-9a12-b63a0de02d38",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:cite-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.984649+00:00",
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
          "message_id": "2eab5566-d357-4958-b8eb-c0f712051ae1",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:writer-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.984692+00:00",
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
          "message_id": "f5c0b684-8b93-4070-af3b-96c6759e6127",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "human:dr-patel",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.984731+00:00",
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
          "message_id": "66237f08-d1ca-4921-ac89-7ce44ba79bdd",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:writer-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.984768+00:00",
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
          "message_id": "2f26eb08-f797-48ec-913f-245f6079b5d0",
          "session_id": "sess-paper-draft",
          "sender": {
            "principal_id": "agent:cite-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.984799+00:00",
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
    "presentation": {
      "tagline": "One incident agent wants to apply a fast fix while another sees evidence the fix is wrong.",
      "shared_object": {
        "title": "Shared Work",
        "kind": "incident",
        "label": "Checkout outage response",
        "before": "Hotfix agent proposes cache flush.\nDiagnostics suspect payment gateway 502s.\nRisk of wrong action in production.",
        "after": "Speculative cache fix is rejected.\nDiagnostics continue.\nHotfix agent pivots to gateway investigation."
      },
      "actors": [
        {
          "name": "Diagnostics Agent",
          "role": "Investigates root cause",
          "color": "agent-a"
        },
        {
          "name": "Hotfix Agent",
          "role": "Proposes immediate remediation",
          "color": "agent-b"
        },
        {
          "name": "Jordan",
          "role": "Human SRE arbiter",
          "color": "owner"
        }
      ],
      "steps": [
        {
          "title": "Two Agents React Differently",
          "focus": "shared",
          "summary": "One agent investigates, while the other jumps ahead with a familiar-looking fix.",
          "left_title": "Diagnostics Agent",
          "left_body": "I am checking logs, traces, and metrics before changing production.",
          "right_title": "Hotfix Agent",
          "right_body": "I want to flush checkout cache right now because this resembles a past incident.",
          "status": [
            "Hotfix is only proposed, not executed",
            "The incident is still under review"
          ],
          "protocol": [
            "INTENT_ANNOUNCE",
            "OP_PROPOSE"
          ]
        },
        {
          "title": "MPAC Makes the Risk Explicit",
          "focus": "conflict",
          "summary": "Diagnostics find evidence that the hotfix is pointed at the wrong root cause.",
          "left_title": "Danger Without Coordination",
          "left_body": "A wrong production fix can waste time, hide the actual issue, and make the outage worse.",
          "right_title": "Protocol Response",
          "right_body": "The contradiction is raised as a critical conflict and escalated to the human arbiter.",
          "status": [
            "Conflict severity: critical",
            "Escalated to SRE"
          ],
          "protocol": [
            "CONFLICT_REPORT",
            "CONFLICT_ESCALATE"
          ]
        },
        {
          "title": "The Arbiter Stops the Wrong Fix",
          "focus": "governance",
          "summary": "Jordan rejects the proposed cache flush and resolves the conflict in favor of further diagnosis.",
          "left_title": "Human Decision",
          "left_body": "Do not execute the cache flush. Continue investigation and pivot toward the payment gateway.",
          "right_title": "Governance Effect",
          "right_body": "The speculative action is formally rejected instead of silently ignored or accidentally applied.",
          "status": [
            "Proposed fix rejected",
            "Root-cause investigation remains active"
          ],
          "protocol": [
            "OP_REJECT",
            "RESOLUTION"
          ]
        },
        {
          "title": "The Agents Re-align and Continue",
          "focus": "outcome",
          "summary": "The hotfix agent withdraws its old plan and starts investigating the real failure domain.",
          "left_title": "Old Path",
          "left_body": "Cache-flush plan is withdrawn.",
          "right_title": "New Path",
          "right_body": "A new intent begins around payment gateway connectivity.",
          "status": [
            "Production stayed safer",
            "Recovery work continues with better alignment"
          ],
          "protocol": [
            "INTENT_WITHDRAW",
            "INTENT_ANNOUNCE"
          ]
        }
      ],
      "outcome": {
        "title": "Why MPAC Helped",
        "bullets": [
          "A risky production action was intercepted before execution.",
          "Escalation gave the SRE enough context to make a fast decision.",
          "The losing agent did not just stop; it pivoted into useful work."
        ]
      }
    },
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
          "message_id": "ca2c1708-2f6d-4c58-a956-655e437a2a8e",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "service:alertmanager",
            "principal_type": "service"
          },
          "ts": "2026-03-30T03:59:38.985141+00:00",
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
          "message_id": "b0ee2cba-85ee-4502-a89a-ea5ce0819e64",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "human:jordan",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.985176+00:00",
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
          "message_id": "42be5c87-a697-49da-a0ed-4a67a3d31cd5",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:diag-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.985208+00:00",
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
          "message_id": "b35530f9-060b-48a4-b10a-80df8d8adf3a",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:hotfix-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.985240+00:00",
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
          "message_id": "d2a70de8-47db-478d-807f-43b48ff21d5f",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:diag-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.985273+00:00",
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
          "message_id": "f676cd7e-011e-49ce-ba96-988da20a5026",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:hotfix-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.985318+00:00",
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
          "message_id": "47411bc0-5cd7-45b9-b7b9-d268d0fa1c87",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:hotfix-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.985373+00:00",
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
          "message_id": "995b58a5-41b0-43b6-b92e-1a50e6ca94c5",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:diag-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.985405+00:00",
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
          "message_id": "47756e09-40c2-4084-bd87-cba5327ff2cf",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:diag-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.985446+00:00",
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
          "message_id": "772605bb-04b6-4a1b-ac2d-4cc6d15eca6a",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "human:jordan",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.985471+00:00",
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
          "message_id": "02448846-0a1e-45b4-9163-fe110a3f743b",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "human:jordan",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.985496+00:00",
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
          "message_id": "d652a36e-a809-45fa-b718-1cb8c1989a33",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:hotfix-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.985531+00:00",
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
          "message_id": "6d88663c-94ea-4c08-8bb6-c2b627a5c3b5",
          "session_id": "sess-incident-4521",
          "sender": {
            "principal_id": "agent:hotfix-1",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.985554+00:00",
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
    "presentation": {
      "tagline": "Two teams with six agents share one codebase and one fragile API boundary.",
      "shared_object": {
        "title": "Shared Work",
        "kind": "code",
        "label": "Dashboard feature across frontend, backend, and shared API contract",
        "before": "Frontend and backend agents both want to touch api/dashboard.openapi.yaml.\nLater, the implementation drifts from the spec.",
        "after": "Contract ownership is sequenced, routes are superseded cleanly, and both test agents validate the final version."
      },
      "actors": [
        {
          "name": "Alice Team",
          "role": "Frontend owner plus UI, state, and test agents",
          "color": "agent-a"
        },
        {
          "name": "Bob Team",
          "role": "Backend owner plus API, DB, and test agents",
          "color": "agent-b"
        },
        {
          "name": "Shared Contract",
          "role": "OpenAPI file both teams depend on",
          "color": "shared"
        }
      ],
      "steps": [
        {
          "title": "Parallel Work Starts Across Two Teams",
          "focus": "shared",
          "summary": "Six agents fan out across database, API, UI, state, and tests.",
          "left_title": "Backend Team",
          "left_body": "Database and API agents move on schema and endpoints.",
          "right_title": "Frontend Team",
          "right_body": "UI and state agents prepare components and client-side integration.",
          "status": [
            "Parallelism is good",
            "Shared API contract is a risky boundary"
          ],
          "protocol": [
            "INTENT_ANNOUNCE",
            "INTENT_ANNOUNCE",
            "INTENT_ANNOUNCE"
          ]
        },
        {
          "title": "Both Teams Reach for the Same Boundary File",
          "focus": "conflict",
          "summary": "The frontend state agent and backend API agent both need the shared OpenAPI spec.",
          "left_title": "Why This Hurts",
          "left_body": "If both sides edit the contract at once, each team can leave with a different understanding of the API.",
          "right_title": "What MPAC Changes",
          "right_body": "The contract conflict becomes a first-class object before either side silently diverges.",
          "status": [
            "Conflict category: scope overlap",
            "Cross-team coordination required"
          ],
          "protocol": [
            "CONFLICT_REPORT"
          ]
        },
        {
          "title": "Humans Negotiate the Boundary",
          "focus": "governance",
          "summary": "Bob proposes one ownership model, Alice pushes back, and they converge on sequential shared writes.",
          "left_title": "Negotiation",
          "left_body": "Backend writes the core spec first. Frontend then adds its extensions afterward.",
          "right_title": "Protocol Benefit",
          "right_body": "This is not a hidden Slack agreement. It becomes explicit, attributable, and visible to every agent.",
          "status": [
            "Negotiated resolution",
            "Shared boundary gets an execution order"
          ],
          "protocol": [
            "RESOLUTION",
            "CONFLICT_ACK",
            "RESOLUTION",
            "CONFLICT_ACK"
          ]
        },
        {
          "title": "A Second Problem Appears Later",
          "focus": "conflict",
          "summary": "The backend implementation drifts from the agreed spec, and a test agent catches it.",
          "left_title": "Mismatch",
          "left_body": "Routes use offset pagination while the spec and frontend expect cursor pagination.",
          "right_title": "Recovery",
          "right_body": "Instead of losing the history, the wrong route commit is explicitly superseded and replaced.",
          "status": [
            "Cross-team bug detected",
            "Old operation preserved for audit"
          ],
          "protocol": [
            "CONFLICT_REPORT",
            "RESOLUTION",
            "OP_SUPERSEDE",
            "OP_COMMIT"
          ]
        },
        {
          "title": "The System Stabilizes",
          "focus": "outcome",
          "summary": "Once the shared boundary is settled, both teams' tests run against the corrected contract.",
          "left_title": "Backend Tests",
          "left_body": "Integration tests confirm routes and pagination behavior.",
          "right_title": "Frontend Tests",
          "right_body": "Component and hook tests confirm the client matches the contract.",
          "status": [
            "Final contract is aligned",
            "Both teams can trust the same shared state"
          ],
          "protocol": [
            "OP_COMMIT",
            "OP_COMMIT",
            "GOODBYE"
          ]
        }
      ],
      "outcome": {
        "title": "Why MPAC Helped",
        "bullets": [
          "It gave two teams a structured way to negotiate one shared boundary file.",
          "It preserved an audit trail when the backend implementation had to be corrected.",
          "It let test agents surface cross-team breakage early enough to recover cleanly."
        ]
      }
    },
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
          "message_id": "d804e63e-e86c-47fa-ae1c-ed345526a001",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "human:alice",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.985857+00:00",
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
          "message_id": "c0cd64ec-657f-43de-8c64-ee8e53c35750",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "human:bob",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.985893+00:00",
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
          "message_id": "b774b502-61b7-4fb1-b8f6-65717fa938a5",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-ui",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.985926+00:00",
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
          "message_id": "9cfe9d1a-8832-4326-848a-cd995e5b857d",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-state",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.985956+00:00",
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
          "message_id": "5508f900-6339-4e32-b968-f4df22c2f9a3",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-test",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.985987+00:00",
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
          "message_id": "1d7a7206-bfd9-43b8-a132-26453fc8299c",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-api",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986017+00:00",
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
          "message_id": "d67a7b39-9599-459b-879b-a5ca781a452b",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-db",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986047+00:00",
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
          "message_id": "267169de-92fa-4426-9a06-d8e2b33a510d",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-test",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986076+00:00",
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
          "message_id": "530744c3-82a7-47a9-97d0-6b5ee0be45b7",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-db",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986111+00:00",
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
          "message_id": "1056b9eb-1aec-46d1-8e90-0a1dc71a6c13",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-api",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986150+00:00",
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
          "message_id": "3cd13534-da89-4982-b204-b74ba313b626",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-test",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986189+00:00",
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
          "message_id": "34299df6-d241-4e8a-980c-491541d5cf32",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-ui",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986228+00:00",
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
          "message_id": "7ddd8cdf-ac3b-4515-9541-4cc7305e1e30",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-state",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986277+00:00",
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
          "message_id": "bd2dcaf8-3da9-4788-a3e1-fac69cd70cc8",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-test",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986319+00:00",
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
          "message_id": "2791b810-dcc9-4d51-aa00-a41491ead0a4",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-state",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986356+00:00",
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
          "message_id": "3a458c22-160f-462a-b24b-78a9006f3e02",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "human:bob",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.986392+00:00",
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
          "message_id": "6d6a27bc-4ddf-4a69-8f91-a22e18df73d4",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-state",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986425+00:00",
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
          "message_id": "bc896c26-b928-4d3b-b9a1-4f28bc5887ff",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "human:alice",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.986447+00:00",
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
          "message_id": "66925f72-786e-48d6-b8df-ae21a858bfd4",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "human:bob",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.986478+00:00",
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
          "message_id": "9999cbc9-7cc7-46b5-bf75-eb7ea1317fa3",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-db",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986500+00:00",
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
          "message_id": "42cc01e2-a05c-4102-90f3-06a4ba0b31d8",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-api",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986528+00:00",
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
          "message_id": "2022601b-64d7-456c-87f2-0ebfaa80b1cd",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-api",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986555+00:00",
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
          "message_id": "601c831f-b045-428b-a43f-564b1707a173",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-ui",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986582+00:00",
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
          "message_id": "c946c033-46dc-4aae-bb6b-b869c998454a",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-state",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986609+00:00",
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
          "message_id": "717b5f8c-1933-49cb-b00a-abf1d529ab7b",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-state",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986636+00:00",
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
          "message_id": "84692030-a203-4d45-89b2-7d74833d0e70",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-test",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986663+00:00",
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
          "message_id": "efb338d1-368c-4466-9221-286fccd74804",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "human:bob",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.986699+00:00",
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
          "message_id": "d09984a3-c234-4591-bf80-e1c56b37c3d3",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-api",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986731+00:00",
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
          "message_id": "fd699bea-88ef-4502-8872-65ffcbd0e027",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-api",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986757+00:00",
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
          "message_id": "ae6eb8b9-b639-47c0-b541-a290bd5e47fd",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-test",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986801+00:00",
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
          "message_id": "c8034127-75a6-4674-893a-ccf387c697d1",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:alice-test",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986829+00:00",
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
          "message_id": "c5c58959-6453-4942-9002-3fa0cd64c46d",
          "session_id": "sess-dashboard-feature",
          "sender": {
            "principal_id": "agent:bob-test",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.986857+00:00",
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
    "presentation": {
      "tagline": "Four travel agents plan one trip, but time, budget, and family priorities all collide.",
      "shared_object": {
        "title": "Shared Work",
        "kind": "planner",
        "label": "Family trip itinerary, budget, and bookings",
        "before": "Everyone has different goals for the same days and the same money.\nNo bookings are finalized yet.",
        "after": "The family gets one coherent itinerary with approved bookings and a budget-conscious compromise."
      },
      "actors": [
        {
          "name": "Parents",
          "role": "Owners and final decision-makers",
          "color": "owner"
        },
        {
          "name": "Kids' Agents",
          "role": "Propose shopping and anime activities",
          "color": "agent-a"
        },
        {
          "name": "Travel Agents",
          "role": "Propose dining, transport, and itinerary bookings",
          "color": "agent-b"
        }
      ],
      "steps": [
        {
          "title": "Everyone Brings Their Own Priorities",
          "focus": "shared",
          "summary": "Dad wants culture, Mom wants food, Lily wants shopping, and Max wants anime and gaming.",
          "left_title": "What Makes This Hard",
          "left_body": "The same trip days and the same household budget must satisfy four different people.",
          "right_title": "Why Agents Help",
          "right_body": "Each person can explore ideas through their own agent without immediately committing the whole family.",
          "status": [
            "Four overlapping plans",
            "No bookings committed yet"
          ],
          "protocol": [
            "INTENT_ANNOUNCE",
            "INTENT_ANNOUNCE",
            "INTENT_ANNOUNCE",
            "INTENT_ANNOUNCE"
          ]
        },
        {
          "title": "Conflicts Surface Before Anyone Books Anything",
          "focus": "conflict",
          "summary": "The agents uncover schedule collisions and a budget overrun across the whole plan.",
          "left_title": "Schedule Conflicts",
          "left_body": "Day 5 cannot be both Hiroshima and Tokyo. Lily and Max also want overlapping time blocks.",
          "right_title": "Budget Conflict",
          "right_body": "Taken together, the family's plans exceed the target budget.",
          "status": [
            "Time contention",
            "Budget contention"
          ],
          "protocol": [
            "CONFLICT_REPORT",
            "CONFLICT_REPORT",
            "CONFLICT_REPORT"
          ]
        },
        {
          "title": "Parents Resolve the Family Tradeoffs",
          "focus": "governance",
          "summary": "The parents merge everyone's priorities into a compromise itinerary and trim one expensive dinner.",
          "left_title": "Schedule Resolution",
          "left_body": "They restructure Day 4 and Day 5 so both kids still get their priorities and Hiroshima moves to a different day.",
          "right_title": "Budget Resolution",
          "right_body": "They keep the important experiences but replace the expensive omakase dinner with a cheaper option.",
          "status": [
            "Conflicts resolved by owners",
            "Compromise keeps most intents alive"
          ],
          "protocol": [
            "RESOLUTION",
            "CONFLICT_ACK",
            "RESOLUTION",
            "RESOLUTION"
          ]
        },
        {
          "title": "Agents Update the Plan",
          "focus": "outcome",
          "summary": "Each travel agent revises its intent to match the agreed schedule and budget.",
          "left_title": "What Changes",
          "left_body": "Dates move, activities are re-ordered, and the dining budget drops.",
          "right_title": "Why It Matters",
          "right_body": "The family now has aligned plans before any non-refundable booking is made.",
          "status": [
            "Revised intents are aligned",
            "Booking stage can begin safely"
          ],
          "protocol": [
            "INTENT_UPDATE",
            "INTENT_UPDATE",
            "INTENT_UPDATE",
            "INTENT_UPDATE"
          ]
        },
        {
          "title": "Proposals Become Approved Bookings",
          "focus": "outcome",
          "summary": "Agents propose reservations, but only the parents commit them.",
          "left_title": "Governance in Practice",
          "left_body": "The kids' agents can suggest tickets, but they cannot spend the family budget on their own.",
          "right_title": "Final Result",
          "right_body": "Parents approve the bookings and the final itinerary is committed once everything is coherent.",
          "status": [
            "Proposal power and commit power are separated",
            "Final plan is executable"
          ],
          "protocol": [
            "OP_PROPOSE",
            "OP_COMMIT",
            "OP_COMMIT",
            "OP_COMMIT"
          ]
        }
      ],
      "outcome": {
        "title": "Why MPAC Helped",
        "bullets": [
          "The family caught schedule and budget conflicts before buying tickets.",
          "Parents stayed in control of final commitments without silencing the kids' preferences.",
          "The final itinerary emerged from structured coordination, not chaos."
        ]
      }
    },
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
          "message_id": "c5e0d3cf-f340-4307-ac58-911276e5de05",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:dad",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.987573+00:00",
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
          "message_id": "b7dc0e74-7f3e-4520-836d-f1e96654cfe7",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:mom",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.987611+00:00",
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
          "message_id": "d9b18fbb-95b3-4df3-9d4f-e925a87a98e8",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:lily",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.987640+00:00",
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
          "message_id": "581fb062-40a8-4bb4-9d60-3a443371b0c9",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:max",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.987668+00:00",
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
          "message_id": "bf076558-09fc-44c3-93ce-33f4db75fc62",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:dad-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.987696+00:00",
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
          "message_id": "7732a27e-773b-4bf9-9452-49c8c9102032",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:mom-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.987725+00:00",
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
          "message_id": "5e1be62b-caef-40b8-aa81-7a0d3ed37a3e",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:lily-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.987753+00:00",
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
          "message_id": "672cebdf-5c4c-4146-a102-9ddcf1fb7e2c",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:max-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.987781+00:00",
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
          "message_id": "9e4e7537-2859-4311-90d5-812af48bfcd4",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:dad-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.987812+00:00",
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
          "message_id": "a4499f2c-aa08-4ccc-b8db-b3dd06afd0a6",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:mom-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.987851+00:00",
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
          "message_id": "e99fd230-5cc1-4439-a02d-bd121f926e27",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:lily-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.987888+00:00",
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
          "message_id": "5cf10ba7-58ad-4f81-b9fa-09d7267d92bb",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:max-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.987924+00:00",
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
          "message_id": "5951fff6-ee4b-4653-ab4f-a672879b87af",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:mom-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.987963+00:00",
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
          "message_id": "e24f3d42-8607-4f15-a415-2b2186992e62",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:dad-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.987997+00:00",
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
          "message_id": "2c6067ed-b24e-4cda-a0a3-ae71f9772da3",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:mom-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.988032+00:00",
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
          "message_id": "ecc9eefb-c460-44c3-bd90-18368f41e640",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:mom",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.988069+00:00",
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
          "message_id": "35903dcd-a699-4365-ab31-2b6fde468c47",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:dad",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.988101+00:00",
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
          "message_id": "1e4b25d5-a3d7-4038-9ebf-4d62eb139ed2",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:mom",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.988122+00:00",
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
          "message_id": "72384fb4-dd97-45e2-b4a4-b0a05155191d",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:dad",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.988153+00:00",
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
          "message_id": "c97a99d3-1ab5-4f1f-956a-d5a9d3126430",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:dad-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.988187+00:00",
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
          "message_id": "a7781364-a5af-41ce-ba72-914b120d7aed",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:mom-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.988226+00:00",
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
          "message_id": "b7068f16-176b-4710-ab05-909a8e3ebe1c",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:lily-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.988262+00:00",
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
          "message_id": "a86e3e1c-1aaf-4da2-b6eb-da164a78bb91",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:max-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.988298+00:00",
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
          "message_id": "c0248933-a59f-4fd8-aada-e44245cb6c1c",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:mom-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.988333+00:00",
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
          "message_id": "41b9f8ed-131a-4669-9b4e-665baa140469",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:lily-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.988361+00:00",
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
          "message_id": "57ad3525-883f-4388-bc7c-9a2be9157b67",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:dad-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.988388+00:00",
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
          "message_id": "54397f49-928f-4ef2-9170-6c8edac94401",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:mom",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.988417+00:00",
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
          "message_id": "2caf3ce7-adcc-45ba-b4b4-0bfec9d48d04",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:mom",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.988449+00:00",
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
          "message_id": "9371a1f9-50dc-441d-9ca3-49090a6f7edd",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "human:dad",
            "principal_type": "human"
          },
          "ts": "2026-03-30T03:59:38.988477+00:00",
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
          "message_id": "5ae6f09c-c37d-4707-809a-367c0a97f1ad",
          "session_id": "sess-japan-trip-2026",
          "sender": {
            "principal_id": "agent:dad-travel",
            "principal_type": "agent"
          },
          "ts": "2026-03-30T03:59:38.988504+00:00",
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
