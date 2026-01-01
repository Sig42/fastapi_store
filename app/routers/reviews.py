from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import Review as ReviewSchema, ReviewCreate
from app.models.reviews import Review as ReviewModel
from app.models.products import Product as ProductModel
from app.models.users import User as UserModel
from app.db_depends import get_async_db
from app.auth import get_current_buyer, get_current_user


router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/", response_model=list[ReviewSchema], status_code=status.HTTP_200_OK)
async def get_all_reviews(db: AsyncSession = Depends(get_async_db)):
    pre_revs = await db.scalars(
        select(ReviewModel).where(ReviewModel.is_active == True)
    )
    revs = pre_revs.all()
    return revs


@router.get("products/{product_id}/reviews", response_model=list[ReviewSchema],  status_code=status.HTTP_200_OK)
async def get_review(product_id: int, db: AsyncSession = Depends(get_async_db)):
    pre_product = await db.scalars(
        select(ProductModel).where(ProductModel.id == product_id, ProductModel.is_active == True)
    )
    product = pre_product.first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wrong product's id")

    pre_revs = await db.scalars(
        select(ReviewModel).where(ReviewModel.product_id == product_id, ReviewModel.is_active == True)
    )
    revs = pre_revs.all()
    return revs


@router.post("/reviews", response_model=ReviewSchema, status_code=status.HTTP_201_CREATED)
async def post_review(body_review: ReviewCreate,
                      buyer: UserModel = Depends(get_current_buyer),
                      db: AsyncSession = Depends(get_async_db)):
    """
        Check out if product exists
    """
    pre_product = await db.scalars(
        select(ProductModel).where(ProductModel.id == body_review.product_id,
                                               ProductModel.is_active == True)
    )
    product = pre_product.first()
    if not product:
        HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wrong product's id")

    """
        Check out if user exists and role is buyer
    """
    pre_buyer = await db.scalars(
        select(UserModel).where(UserModel.id == buyer.id, UserModel.is_active == True)
    )
    buyer = pre_buyer.first()
    if not buyer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only active buyer can perform this action")
    new_review = ReviewModel(**body_review.model_dump(), user_id = buyer.id)

    """
        Update product's rating
    """
    db.add(new_review)
    await db.commit()
    pre_rate = await db.execute(
        select(func.avg(ReviewModel.grade)).where(ReviewModel.product_id == product.id,
                                                              ReviewModel.is_active == True
        )
    )
    avg_rating = pre_rate.scalar()
    await db.execute(update(ProductModel).where(ProductModel.id == product.id).values(rating=avg_rating))
    await db.commit()
    await db.refresh(new_review)
    return new_review


@router.delete("/{review_id}", status_code=status.HTTP_200_OK)
async def delete_review(review_id: int,
                        db: AsyncSession = Depends(get_async_db),
                        current_user: UserModel = Depends(get_current_user)) -> dict:

    """
        Check out if review exists
    """
    pre_rev = await db.scalars(
        select(ReviewModel).where(ReviewModel.id == review_id,
                                  ReviewModel.is_active == True)
    )
    review = pre_rev.first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wrong id")

    """
        Check out if current user is owner or admin
    """
    if not (review.user_id == current_user.id or current_user.email == "admin@example.com"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owner or admin can delete review")

    await db.execute(
        update(ReviewModel).where(ReviewModel.id == review_id).values(is_active=False)
    )
    await db.commit()
    return {"message": "Review deleted"}
