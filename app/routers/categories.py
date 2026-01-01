from fastapi import APIRouter,Depends, HTTPException, status
from sqlalchemy import select, update
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_200_OK
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.categories import Category as CategoryModel
from app.models.users import User as UserModel
from app.schemas import Category as CategorySchema, CategoryCreate
from app.db_depends import get_async_db
from app.auth import get_admin

router = APIRouter(
    prefix="/categories",
    tags=["categories"])

@router.get("/", response_model=list[CategorySchema], status_code=HTTP_200_OK)
async def get_all_categories(db: AsyncSession = Depends(get_async_db)):
    stmt = select(CategoryModel).where(CategoryModel.is_active == True)
    result = await db.scalars(stmt)
    categories = result.all()
    return categories

@router.post("/", response_model=CategorySchema, status_code=status.HTTP_201_CREATED)
async def create_category(category: CategoryCreate,
                          db: AsyncSession = Depends(get_async_db),
                          is_admin: UserModel = Depends(get_admin)):
    if category.parent_id is not None:
        """
            Check that category's parent is not inactive or failed
        """
        pre_parent = await db.scalars(
            select(CategoryModel).where(CategoryModel.id == category.parent_id,
                                                    CategoryModel.is_active == True)
        )
        parent = pre_parent.first()
        if parent is None:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Category parent not found")
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin can perform this action")
    db_category = CategoryModel(**category.model_dump())
    db.add(db_category)
    await db.commit()
    return db_category

@router.put("/{category_id}", response_model=CategorySchema)
async def update_category(category_id: int, category: CategoryCreate, db: AsyncSession = Depends(get_async_db)):
    stmt = select(CategoryModel).where(CategoryModel.id == category_id,
                                       CategoryModel.is_active == True)
    result = await db.scalars(stmt)
    db_category = result.first()

    if db_category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    if category.parent_id is not None:
        parent_stmt = select(CategoryModel).where(CategoryModel.id == category.parent_id,
                                                  CategoryModel.is_active == True)
        result = await db.scalars(parent_stmt)
        parent = result.first()
        if parent is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent category not found")

    await db.execute(update(CategoryModel).where(CategoryModel.id == category_id).values(**category.model_dump()))
    await db.commit()
    return db_category

@router.delete("/{category_id}", status_code=status.HTTP_200_OK)
async def delete_category(category_id: int, db: AsyncSession = Depends(get_async_db)):
    stmt = select(CategoryModel).where(CategoryModel.is_active == True,
                                       CategoryModel.id == category_id)
    result = await db.scalars(stmt)
    category = result.first()
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Category not found')
    await db.execute(update(CategoryModel).where(CategoryModel.id == category_id).values(is_active=False))
    await db.commit()
    return category
