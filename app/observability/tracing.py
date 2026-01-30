import io
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

def setup_tracer():
    """
    Configures and sets up the OpenTelemetry tracer to export to a JSON file.
    """
    resource = Resource(attributes={
        "service.name": "rag-observability"
    })

    # Configure the ConsoleSpanExporter to write to a JSON file
    trace_file = open("traces.json", "w")
    json_exporter = ConsoleSpanExporter(out=trace_file)

    # Set up the TracerProvider and BatchSpanProcessor
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(json_exporter))

    # Set the global TracerProvider
    trace.set_tracer_provider(tracer_provider)
