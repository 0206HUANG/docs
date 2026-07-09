import uuid
from typing import Generic, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError

T = TypeVar("T")


class TenantBaseRepo(Generic[T]):
    """Base repository that enforces tenant isolation on every query."""

    def __init__(self, model: Type[T], db: AsyncSession, tenant_id: uuid.UUID):
        self.model = model
        self.db = db
        self.tenant_id = tenant_id

    def _base_query(self):
        return select(self.model).where(self.model.tenant_id == self.tenant_id)

    async def get_by_id(self, id: uuid.UUID, options: list | None = None) -> T:
        q = self._base_query().where(self.model.id == id)
        if options:
            q = q.options(*options)
        result = await self.db.execute(q)
        obj = result.scalar_one_or_none()
        if not obj:
            raise NotFoundError(self.model.__name__)
        return obj

    async def get_all(self, **filters) -> list[T]:
        q = self._base_query()
        for k, v in filters.items():
            q = q.where(getattr(self.model, k) == v)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def create(self, **kwargs) -> T:
        obj = self.model(tenant_id=self.tenant_id, **kwargs)
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, id: uuid.UUID, **kwargs) -> T:
        obj = await self.get_by_id(id)
        for k, v in kwargs.items():
            setattr(obj, k, v)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete(self, id: uuid.UUID) -> None:
        obj = await self.get_by_id(id)
        await self.db.delete(obj)
        await self.db.flush()
