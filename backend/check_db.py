import asyncio
import asyncpg

async def check_schema():
    conn = await asyncpg.connect(
        'postgresql://postgres:AmanKumar%403347@db.mlvbodeurnudfbukfdgk.supabase.co:5432/postgres'
    )
    
    # List all tables in public and auth schemas
    tables = await conn.fetch("""
        SELECT table_name, table_schema 
        FROM information_schema.tables 
        WHERE table_schema IN ('public', 'auth')
        ORDER BY table_schema, table_name
    """)
    print("=== ALL TABLES (public + auth) ===")
    for t in tables:
        print(f"  {t['table_schema']}.{t['table_name']}")
    
    # Check alembic version
    try:
        ver = await conn.fetch("SELECT version_num FROM alembic_version")
        print("\n=== ALEMBIC VERSION ===")
        for v in ver:
            print(f"  {v['version_num']}")
    except Exception as e:
        print(f"\n  No alembic_version: {e}")

    # Check if specific tables exist
    for tbl in ['users', 'media_files', 'transcripts', 'summaries']:
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = $1
            )
        """, tbl)
        print(f"\n  public.{tbl} exists: {exists}")

    await conn.close()

asyncio.run(check_schema())
