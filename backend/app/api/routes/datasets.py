"""Read-only benchmark metadata API; import is an explicit server-side CLI step."""

from fastapi import APIRouter, HTTPException

from app.models.schemas import DatasetMetadata
from app.storage.database import repository

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=list[DatasetMetadata])
async def list_datasets():
    return repository.list_datasets()


@router.get("/{dataset_id}", response_model=DatasetMetadata)
async def get_dataset(dataset_id: str):
    dataset = repository.get_dataset(dataset_id)
    if dataset is None:
        raise HTTPException(404, "Benchmark dataset not registered")
    return dataset
