"""Pagination helper for supply chain views."""
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


def paginate_queryset(request, queryset, per_page=25, page_param='page'):
    paginator = Paginator(queryset, per_page)
    page_num = request.GET.get(page_param, 1)
    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    return page_obj, paginator


def paginate_list(request, items, per_page=25, page_param='page'):
    paginator = Paginator(items, per_page)
    page_num = request.GET.get(page_param, 1)
    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    return page_obj, paginator


def smart_page_range(page_obj, paginator):
    current = page_obj.number
    num_pages = paginator.num_pages
    if num_pages <= 7:
        return list(range(1, num_pages + 1))
    pages = set()
    pages.update(range(1, 2))
    pages.update(range(num_pages, num_pages + 1))
    pages.update(range(max(1, current - 2), min(num_pages, current + 2) + 1))
    result = []
    prev = None
    for p in sorted(pages):
        if prev is not None and p - prev > 1:
            result.append('...')
        result.append(p)
        prev = p
    return result
