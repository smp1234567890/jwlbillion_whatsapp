"""
Shopify Products Router
Fetches live products directly from the linked Shopify store on demand without saving to DB.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import auth
import models
from database import get_db
from services.shopify_service import fetch_shopify_products, sync_shopify_customers_and_orders

router = APIRouter(prefix="/api/shopify", tags=["Shopify Products"])


@router.post("/sync-customers")
def sync_shopify_customers(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    On-demand synchronization of Shopify customers and orders into the CRM Contact directory.
    """
    return sync_shopify_customers_and_orders(db=db)


@router.get("/products")
def get_live_shopify_products(
    limit: int = Query(250, ge=1, le=250),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Fetches real-time products directly from Shopify storefront API.
    Zero database persistence as per architectural requirement.
    """
    return fetch_shopify_products(limit=limit)

