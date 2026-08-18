from contracts.schemas import ClinicalEvent, Step1Output

from .abbreviations import expand_field
from .adapters import NLPAdapterBundle, build_adapter_bundle
from .event_builder import build_clinical_event
from .preprocess import preprocess_step1_output
from .validation import validate_events
from .terminology import normalize_field, normalize_terminology


class ClinicalNLPPipeline:
    def __init__(self, adapters: NLPAdapterBundle | None = None) -> None:
        self.adapters = adapters or build_adapter_bundle()

    def process(self, step1_output: Step1Output) -> list[ClinicalEvent]:
        events: list[ClinicalEvent] = []
        for preprocessed in preprocess_step1_output(step1_output):
            expanded = expand_field(preprocessed)
            if hasattr(self.adapters.ner, "extract_with_enrichment"):
                entities = self.adapters.ner.extract_with_enrichment(expanded)
            else:
                entities = self.adapters.ner.extract(expanded.processed_text)
            for entity in entities:
                terminology = normalize_terminology(entity.text)
                if entity.entity_type == "clinical_statement":
                    # A statement fallback represents the whole processed
                    # field, so normalize that field instead of referencing a
                    # non-existent variable (which previously crashed on
                    # otherwise valid free-text input).
                    terminology = normalize_field(expanded)
                context = self.adapters.contextualization.contextualize(
                    expanded.processed_text,
                    entity.text,
                )
                events.append(
                    build_clinical_event(
                        field=expanded,
                        terminology=terminology,
                        entity=entity,
                        context=context,
                        source_document_id=step1_output.document_id,
                        input_modality=step1_output.input_modality,
                        source_language=step1_output.source_language,
                        translation_confidence=step1_output.translation_confidence,
                    )
                )

        return validate_events(
            events,
            expected_source_document_id=step1_output.document_id,
        )
