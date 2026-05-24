from src.ingest_docs import load_markdown_chunks


def test_markdown_chunks_preserve_section_metadata():
    chunks = load_markdown_chunks()
    target = next(chunk for chunk in chunks if chunk.section_heading == "Escalation Timeline")
    assert target.source_file == "shipment_escalation_sop.md"
    assert target.start_line == 104
    assert target.end_line == 118
    assert "Shipment Delay Escalation Standard Operating Procedure" in target.section_path


def test_prompt_injection_appendix_is_tagged():
    chunks = load_markdown_chunks()
    target = next(chunk for chunk in chunks if "Prompt Injection" in chunk.section_heading)
    assert target.security_test_artifact is True
