import functools
import asyncio
from typing import Optional, Any, Callable
from ..config.settings import settings
from .logger import adk_logger

# Lazy-loaded OTEL components
_tracer = None

def get_tracer():
    """
    Returns the OpenTelemetry tracer if enabled, otherwise a no-op tracer.
    """
    global _tracer
    if not settings.enable_telemetry:
        return None
    
    if _tracer is not None:
        return _tracer

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        
        resource = Resource.create({"service.name": "litellm-adk"})
        provider = TracerProvider(resource=resource)
        
        if settings.otel_exporter_endpoint:
             from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
             processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint))
             provider.add_span_processor(processor)
        
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("litellm-adk")
        return _tracer
    except ImportError:
        adk_logger.warning("OpenTelemetry components not found. Tracing disabled. Install with 'pip install litellm-adk[telemetry]'")
        return None

def trace_span(name: str):
    """
    A decorator/context manager to wrap functions in an OTEL span.
    """
    def decorator(func: Callable):
        if not settings.enable_telemetry:
            return func

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            if not tracer:
                return await func(*args, **kwargs)
            
            with tracer.start_as_current_span(name) as span:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.status.Status(trace.status.StatusCode.ERROR))
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer()
            if not tracer:
                return func(*args, **kwargs)
            
            with tracer.start_as_current_span(name) as span:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    span.record_exception(e)
                    # Note: We don't import 'trace' globally to avoid dep issues
                    from opentelemetry import trace as otel_trace
                    span.set_status(otel_trace.status.Status(otel_trace.status.StatusCode.ERROR))
                    raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator
