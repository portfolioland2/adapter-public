from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter  # type: ignore
from opentelemetry.sdk.resources import Resource, SERVICE_NAME  # type: ignore
from opentelemetry.sdk.trace import TracerProvider  # type: ignore
from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore

from src.config import settings


def init_tracer() -> TracerProvider:
    resource = Resource(
        attributes={
            SERVICE_NAME: "rkeeper-adapter",
        }
    )
    jaeger_exporter = JaegerExporter(
        agent_host_name=settings.OPENTELEMETRY_AGENT_NAME,
        timeout=5,
        collector_endpoint=settings.OPENTELEMETRY_COLLECTOR_ENDPOINT,
        username=settings.OPENTELEMETRY_USERNAME,
        password=settings.OPENTELEMETRY_PASSWORD,
    )
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(jaeger_exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    return provider
