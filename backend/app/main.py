"""FastAPI interface for the Customer Churn & Retention Intelligence platform."""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.app import service


app = FastAPI(title="Customer Churn & Retention Intelligence API", version="1.0.0", description="Database-backed analytics for a fictional, synthetic subscription business.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["GET"], allow_headers=["*"])


def _serve(callable_):
    try:
        return callable_()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/overview")
def get_overview():
    return _serve(service.overview)


@app.get("/api/churn")
def get_churn(plan: Optional[str] = None, region: Optional[str] = None):
    return _serve(lambda: service.churn(plan, region))


@app.get("/api/segments")
def get_segments():
    return _serve(service.segments)


@app.get("/api/risk")
def get_risk():
    return _serve(service.risk)


@app.get("/api/customers")
def get_customers(search: Optional[str] = None, risk_segment: Optional[str] = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    return _serve(lambda: service.customer_rows(search, risk_segment, page, page_size))


@app.get("/api/customer/{customer_id}")
def get_customer(customer_id: str):
    detail = _serve(lambda: service.customer_detail(customer_id))
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Customer '{customer_id}' was not found")
    return detail


@app.get("/api/cohorts")
def get_cohorts():
    return _serve(service.cohorts)


@app.get("/api/model")
def get_model():
    return _serve(service.model_metrics)


@app.get("/api/data-quality")
def get_data_quality():
    return _serve(service.quality_report)


@app.get("/api/insights")
def get_insights():
    return _serve(service.insights)
