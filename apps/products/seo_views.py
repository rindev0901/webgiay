import os
from django.http import HttpResponse, FileResponse
from django.conf import settings
from django.utils import timezone
from apps.products.models import Category, Product


def robots_txt(request):
    """Serve robots.txt directly from static files with root domain path."""
    path = os.path.join(settings.BASE_DIR, 'static', 'robots.txt')
    if os.path.exists(path):
        return FileResponse(open(path, 'rb'), content_type='text/plain')
    
    # Fallback hardcoded if file not found
    content = "User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /cart/\nDisallow: /accounts/\nDisallow: /supply/\nSitemap: /sitemap.xml"
    return HttpResponse(content, content_type='text/plain')


def manifest_json(request):
    """Serve manifest.json directly from static files at root domain path."""
    path = os.path.join(settings.BASE_DIR, 'static', 'manifest.json')
    if os.path.exists(path):
        return FileResponse(open(path, 'rb'), content_type='application/json')
    return HttpResponse('{}', content_type='application/json')


def service_worker(request):
    """Serve sw.js directly from static files at root domain path for correct scope."""
    path = os.path.join(settings.BASE_DIR, 'static', 'sw.js')
    if os.path.exists(path):
        return FileResponse(open(path, 'rb'), content_type='application/javascript')
    return HttpResponse('', content_type='application/javascript')


def sitemap_xml(request):
    """Dynamically generate sitemap.xml for landing, catalog, categories, and products."""
    base_url = request.build_absolute_uri('/').rstrip('/')
    
    urls = []
    
    # 1. Static/Main urls
    # Landing page (homepage)
    urls.append({
        'loc': f"{base_url}/",
        'changefreq': 'daily',
        'priority': '1.0'
    })
    # Products catalog list
    urls.append({
        'loc': f"{base_url}/products/",
        'changefreq': 'daily',
        'priority': '0.9'
    })
    
    # 2. Category detail pages
    categories = Category.objects.filter(is_active=True)
    for cat in categories:
        urls.append({
            'loc': f"{base_url}/products/category/{cat.slug}/",
            'changefreq': 'weekly',
            'priority': '0.8'
        })
        
    # 3. Product detail pages
    products = Product.objects.filter(is_active=True).select_related('brand')
    for prod in products:
        # Use updated_at for lastmod if available, otherwise timezone.now() or static date
        lastmod = prod.updated_at.strftime('%Y-%m-%d') if hasattr(prod, 'updated_at') else None
        urls.append({
            'loc': f"{base_url}/products/{prod.slug}/",
            'changefreq': 'weekly',
            'priority': '0.7',
            'lastmod': lastmod
        })

    # Build XML response
    xml_parts = []
    xml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    for url in urls:
        xml_parts.append('  <url>')
        xml_parts.append(f"    <loc>{url['loc']}</loc>")
        if 'lastmod' in url and url['lastmod']:
            xml_parts.append(f"    <lastmod>{url['lastmod']}</lastmod>")
        xml_parts.append(f"    <changefreq>{url['changefreq']}</changefreq>")
        xml_parts.append(f"    <priority>{url['priority']}</priority>")
        xml_parts.append('  </url>')
        
    xml_parts.append('</urlset>')
    
    xml_content = "\n".join(xml_parts)
    return HttpResponse(xml_content, content_type='application/xml')
