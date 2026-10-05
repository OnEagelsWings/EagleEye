# Build 440 case-specific hard-checkpoint test

Use a dedicated synthetic/demo case only.

## Endpoint

With EagleEye running and an authenticated system administrator who also has research access to the qualification case:

\`\`\`
POST /api/build440/cases/{case_id}/qualification/run
\`\`\`

The qualification performs these checks:

1. integrity of all required Phase-19 components, Builds 421–439;
2. the complete synthetic Build-439 investigation-loop case path;
3. the no-forbidden-authority contract;
4. the declared capability boundary for Surface-Web, News, Social and Tor retrieval;
5. persistence and integrity of the Build-440 qualification report.

A successful engineering checkpoint returns:

\`\`\`json
{
  "report": {
    "qualification_result": "pass",
    "engineering_checkpoint_pass": true,
    "live_collection_complete": false,
    "real_world_general_research_ready": false,
    "production_release_ready": false
  }
}
\`\`\`

The last three values being \`false\` are expected at Build 440. They document the remaining implementation boundary rather than causing the technical checkpoint to fail.
