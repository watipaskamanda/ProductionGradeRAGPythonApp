import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  try {
    const { question, currency, user_level } = await request.json()
    
    const response = await fetch('http://localhost:8000/api/v1/query/database', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        question,
        currency: currency || 'MWK',
        user_level: user_level || 'business',
        debug_mode: user_level === 'developer'
      })
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Backend responded with status: ${response.status} - ${errorText}`)
    }
    
    const data = await response.json()
    return NextResponse.json({ 
      response: data.answer,
      table: data.markdown_table,
      chart: data.chart_config 
    })
    
  } catch (error) {
    console.error('Database API error:', error)
    return NextResponse.json(
      { error: `Connection failed: ${error.message}. Make sure FastAPI server is running on localhost:8000` },
      { status: 500 }
    )
  }
}