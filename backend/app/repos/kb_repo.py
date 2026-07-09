import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KBChunk, KBDocument, KBGroup
from app.repos.base import TenantBaseRepo


class KBGroupRepo(TenantBaseRepo[KBGroup]):
    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID):
        super().__init__(KBGroup, db, tenant_id)

    async def find_for_email(self, positioning: str, email_type: str) -> list[KBGroup]:
        result = await self.db.execute(
            select(KBGroup).where(
                KBGroup.tenant_id == self.tenant_id,
                KBGroup.is_active == True,
            )
        )
        groups = list(result.scalars().all())
        matched = []
        for g in groups:
            pos_match = not g.positioning or positioning in g.positioning
            type_match = not g.email_types or email_type in g.email_types
            if pos_match and type_match:
                matched.append(g)
        return matched


class KBChunkRepo:
    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID):
        self.db = db
        self.tenant_id = tenant_id

    async def similarity_search(
        self,
        embedding: list[float],
        group_ids: list[uuid.UUID],
        top_k: int = 5,
        min_score: float = 0.7,
    ) -> list[tuple[KBChunk, float]]:
        if not group_ids:
            return []

        vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
        group_ids_str = ",".join(f"'{g}'" for g in group_ids)

        sql = text(
            "SELECT id, content, chunk_index, document_id, group_id, tenant_id, "
            "1 - (embedding <=> CAST(:vec AS vector)) AS score "
            "FROM kb_chunks "
            "WHERE tenant_id = :tenant_id "
            f"AND group_id IN ({group_ids_str}) "
            "AND embedding IS NOT NULL "
            "AND 1 - (embedding <=> CAST(:vec AS vector)) >= :min_score "
            "ORDER BY embedding <=> CAST(:vec AS vector) "
            "LIMIT :top_k"
        )
        result = await self.db.execute(
            sql,
            {
                "vec": vec_str,
                "tenant_id": str(self.tenant_id),
                "min_score": min_score,
                "top_k": top_k,
            },
        )
        rows = result.fetchall()
        chunks = []
        for row in rows:
            chunk = KBChunk(
                id=row.id,
                content=row.content,
                chunk_index=row.chunk_index,
                document_id=row.document_id,
                group_id=row.group_id,
                tenant_id=uuid.UUID(str(row.tenant_id)),
            )
            chunks.append((chunk, float(row.score)))
        return chunks

    async def add_chunk(self, chunk: KBChunk) -> None:
        self.db.add(chunk)
        await self.db.flush()
