import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.INTERNAL_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const sessionCookie = request.cookies.get('session')?.value;
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (sessionCookie) {
      headers['Cookie'] = `session=${sessionCookie}`;
    }

    const body = await request.text();
    const res = await fetch(`${BACKEND_URL}/api/open-loops/${id}`, {
      method: 'PATCH',
      headers,
      body,
    });

    const data = await res.text();
    return new NextResponse(data, {
      status: res.status,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error: any) {
    return NextResponse.json(
      { detail: `Proxy error: ${error.message}` },
      { status: 502 }
    );
  }
}
