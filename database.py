import asyncpg
import asyncio

class Database:
    def __init__(self, dsn):
        self.dsn = dsn
        self.pool = None

    async def connect(self):
        """Establish a connection pool with PostgreSQL."""
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                self.dsn,
                min_size=1,
                max_size=5,  # reduce to control resource usage
                max_inactive_connection_lifetime=30.0  # closes idle clients faster
            )

    async def close(self):
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()

    async def execute(self, query, *args):
        """Execute a query that doesn't return data (INSERT, UPDATE, DELETE)."""
        async with self.pool.acquire() as conn:
            await conn.execute(query, *args)

    async def fetch(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)  # Fetch multiple rows

    async def fetchrow(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)  # Fetch a single row

    async def fetchval(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)  # Fetch a single value



# Create a single global database instance
db = Database("postgresql://postgres:pokedia_2389@db.urgwtnlyeezkbgbjlqjb.supabase.co:5432/postgres")

# Function to initialize the database at bot startup
async def setup_database():
    await db.connect()

# Function to get the database pool (so other files can use it)
async def get_database_pool():
    """Returns the database pool from the Database instance."""
    if not db.pool:
        await db.connect()
    return db.pool
