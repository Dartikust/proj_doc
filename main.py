from contextlib import asynccontextmanager
from math import ceil
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from db import (
    add_contract,
    delete_contract,
    get_all_contracts,
    get_contract,
    get_filter_options,
    get_stats,
    init_db,
    search_contracts,
    update_contract_fields,
)
from parser import parse_contract

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE = 20 * 1024 * 1024
PAGE_SIZE = 25


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="DocFlow — реестр договоров", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _parse_optional_float(value: str | None):
    if value is None or not value.strip():
        return None
    normalized = value.strip().replace(" ", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def _documents_url(current: dict, **overrides):
    params = dict(current)
    params.update(overrides)
    params = {
        key: value
        for key, value in params.items()
        if value not in (None, "", False)
    }
    query = urlencode(params)
    return "/documents" + (f"?{query}" if query else "")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    contracts = get_all_contracts(limit=5)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "contracts": contracts,
            "stats": get_stats(),
            "error": request.query_params.get("error", ""),
        },
    )


@app.get("/documents", response_class=HTMLResponse)
async def documents_page(
    request: Request,
    q: str = "",
    date_from: str = "",
    date_to: str = "",
    amount_min: str = "",
    amount_max: str = "",
    status: str = "",
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
):
    q = q.strip()
    date_from = date_from.strip()
    date_to = date_to.strip()
    status = status.strip()
    sort = sort if sort in {"created_at", "date", "amount", "number", "filename"} else "created_at"
    order = "asc" if order.lower() == "asc" else "desc"

    amount_min_value = _parse_optional_float(amount_min)
    amount_max_value = _parse_optional_float(amount_max)

    filters = {
        "q": q,
        "date_from": date_from,
        "date_to": date_to,
        "amount_min": amount_min.strip(),
        "amount_max": amount_max.strip(),
        "status": status,
        "sort": sort,
        "order": order,
    }

    offset = (page - 1) * PAGE_SIZE
    contracts, total = search_contracts(
        search=q or None,
        date_from=date_from or None,
        date_to=date_to or None,
        amount_min=amount_min_value,
        amount_max=amount_max_value,
        status=status or None,
        sort=sort,
        order=order,
        limit=PAGE_SIZE,
        offset=offset,
    )

    total_pages = max(1, ceil(total / PAGE_SIZE))
    if page > total_pages and total > 0:
        return RedirectResponse(
            _documents_url(filters, page=total_pages),
            status_code=303,
        )

    def documents_url(**overrides):
        return _documents_url({**filters, "page": page}, **overrides)

    sort_labels = {
        "created_at": "Сначала загруженные",
        "date": "По дате договора",
        "amount": "По сумме",
        "number": "По номеру",
        "filename": "По имени файла",
    }

    active_filter_count = sum(
        bool(value)
        for value in [
            q,
            date_from,
            date_to,
            amount_min.strip(),
            amount_max.strip(),
            status,
        ]
    )

    return templates.TemplateResponse(
        request=request,
        name="documents.html",
        context={
            "contracts": contracts,
            "total": total,
            "filters": filters,
            "options": get_filter_options(),
            "sort_labels": sort_labels,
            "page": page,
            "total_pages": total_pages,
            "page_size": PAGE_SIZE,
            "active_filter_count": active_filter_count,
            "documents_url": documents_url,
        },
    )


@app.post("/upload")
async def upload_contract(file: UploadFile = File(...)):
    original_name = Path(file.filename or "").name
    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        return RedirectResponse(
            url="/?error=Можно загружать только PDF и DOCX",
            status_code=303,
        )

    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        return RedirectResponse(
            url="/?error=Файл слишком большой. Максимум 20 МБ",
            status_code=303,
        )

    stored_name = f"{uuid4().hex}{extension}"
    path = UPLOAD_DIR / stored_name
    path.write_bytes(content)

    parsed = parse_contract(path)
    contract_id = add_contract(
        filename=original_name,
        stored_name=stored_name,
        number=parsed.get("number"),
        contract_date=parsed.get("date"),
        customer=parsed.get("customer"),
        contractor=parsed.get("contractor"),
        amount=parsed.get("amount"),
        raw_text=parsed.get("raw_text"),
        status=parsed.get("status", "Ожидает обработки"),
    )

    return RedirectResponse(url=f"/document/{contract_id}", status_code=303)


@app.get("/document/{contract_id}", response_class=HTMLResponse)
async def document_page(request: Request, contract_id: int):
    contract = get_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Документ не найден")

    return templates.TemplateResponse(
        request=request,
        name="document.html",
        context={"contract": contract},
    )


@app.post("/document/{contract_id}/edit")
async def edit_document(
    contract_id: int,
    number: str = Form(""),
    contract_date: str = Form(""),
    customer: str = Form(""),
    contractor: str = Form(""),
    amount: str = Form(""),
):
    if not get_contract(contract_id):
        raise HTTPException(status_code=404, detail="Документ не найден")

    update_contract_fields(
        contract_id=contract_id,
        number=number.strip() or None,
        contract_date=contract_date.strip() or None,
        customer=customer.strip() or None,
        contractor=contractor.strip() or None,
        amount=amount.strip() or None,
    )
    return RedirectResponse(url=f"/document/{contract_id}", status_code=303)


@app.get("/document/{contract_id}/file")
async def download_file(contract_id: int):
    contract = get_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Документ не найден")

    path = UPLOAD_DIR / contract["stored_name"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")

    return FileResponse(path, filename=contract["filename"])


@app.post("/document/{contract_id}/delete")
async def delete_document(contract_id: int):
    contract = get_contract(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Документ не найден")

    path = UPLOAD_DIR / contract["stored_name"]
    if path.exists():
        path.unlink()

    delete_contract(contract_id)
    return RedirectResponse(url="/documents", status_code=303)
