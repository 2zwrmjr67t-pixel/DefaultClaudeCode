"""
Cliente para a Shopee Affiliate Open API (GraphQL, BR).

[Verificado — fonte: documentação pública/Apify] Endpoint BR, uso de
GraphQL e assinatura HMAC-SHA256.

[Inferência] O formato exato do header de assinatura abaixo segue o
padrão mais comum documentado para essa API (Credential/Signature/
Timestamp), mas NÃO foi testado contra a API real nesta sessão.
Antes de rodar em produção, confirme os campos exatos no Explorer
oficial: https://open-api.affiliate.shopee.co.id/explorer/v2
e ajuste `_build_signature` se necessário.
"""
import hashlib
import time
import os
import requests

GRAPHQL_ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"


class ShopeeAffiliateClient:
    def __init__(self, app_id: str | None = None, app_secret: str | None = None):
        self.app_id = app_id or os.environ["SHOPEE_APP_ID"]
        self.app_secret = app_secret or os.environ["SHOPEE_APP_SECRET"]

    def _build_signature(self, payload: str, timestamp: int) -> str:
        base = f"{self.app_id}{timestamp}{payload}{self.app_secret}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def _headers(self, payload: str) -> dict:
        timestamp = int(time.time())
        signature = self._build_signature(payload, timestamp)
        return {
            "Content-Type": "application/json",
            "Authorization": (
                f"SHA256 Credential={self.app_id}, "
                f"Signature={signature}, Timestamp={timestamp}"
            ),
        }

    def _post(self, query: str, variables: dict) -> dict:
        payload = {"query": query, "variables": variables}
        import json as _json
        payload_str = _json.dumps(payload, separators=(",", ":"))
        resp = requests.post(
            GRAPHQL_ENDPOINT,
            data=payload_str,
            headers=self._headers(payload_str),
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(f"Erro da API Shopee: {data['errors']}")
        return data["data"]

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def get_products_by_keyword(self, keyword: str, limit: int = 20,
                                 sort_type: int = 1) -> list[dict]:
        """sort_type: 1=relevância, 2=vendas, 3=preço maior->menor
        (ordem exata a confirmar no Explorer)."""
        query = """
        query ProductOfferV2($keyword: String, $listType: Int, $sortType: Int, $limit: Int) {
          productOfferV2(keyword: $keyword, listType: $listType, sortType: $sortType, limit: $limit) {
            nodes {
              itemId
              productName
              price
              priceMin
              priceMax
              imageUrl
              shopName
              offerLink
              ratingStar
              sales
            }
          }
        }
        """
        variables = {"keyword": keyword, "listType": 1, "sortType": sort_type, "limit": limit}
        data = self._post(query, variables)
        return data["productOfferV2"]["nodes"]

    def get_product_by_item_id(self, item_id: str, shop_id: str | None = None) -> dict | None:
        query = """
        query ProductOfferV2($itemId: Int64) {
          productOfferV2(itemId: $itemId) {
            nodes {
              itemId
              productName
              price
              priceMin
              priceMax
              imageUrl
              shopName
              offerLink
              ratingStar
              sales
            }
          }
        }
        """
        variables = {"itemId": int(item_id)}
        data = self._post(query, variables)
        nodes = data["productOfferV2"]["nodes"]
        return nodes[0] if nodes else None
