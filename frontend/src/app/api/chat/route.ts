import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  try {
    const { message } = await request.json()
    
    const response = await fetch('http://localhost:8000/api/v1/query', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        question: message,
        top_k: 5
      })
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Backend responded with status: ${response.status} - ${errorText}`)
    }
    
    const data = await response.json()
    return NextResponse.json({ response: data.answer })
    
  } catch (error) {
    console.error('Chat API error:', error)
    return NextResponse.json(
      { error: `Connection failed: ${error.message}. Make sure FastAPI server is running on localhost:8000` },
      { status: 500 }
    )
  }
}