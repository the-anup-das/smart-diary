import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.INTERNAL_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export async function POST(request: NextRequest, { params }: { params: Promise<{ action: string }> }) {
  try {
    const { action } = await params;
    const body = await request.text();

    const res = await fetch(`${BACKEND_URL}/api/auth/${action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      cache: 'no-store',
    });

    const data = await res.text();
    const response = new NextResponse(data, {
      status: res.status,
      headers: { 'Content-Type': res.headers.get('content-type') || 'application/json' },
    });

    // Forward any Set-Cookie headers from the backend
    const setCookie = res.headers.get('set-cookie');
    if (setCookie) {
      response.headers.set('set-cookie', setCookie);
    }

    return response;
  } catch (error: any) {
    return NextResponse.json(
      { detail: `Proxy to backend failed: ${error.message}` },
      { status: 502 }
    );
  }
}
