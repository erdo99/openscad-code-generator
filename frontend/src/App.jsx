import { useState } from 'react'
import axios from 'axios'
import './App.css'

const API_BASE = '/api'

function App() {
  const [image, setImage] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [description, setDescription] = useState('Bu 3D objenin OpenSCAD kodunu üret. Boyutlar, şekiller ve detaylar hakkında açıklama yapabilirsiniz.')
  const [instruction, setInstruction] = useState('')
  const [code, setCode] = useState('')
  const [renderedImage, setRenderedImage] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [improving, setImproving] = useState(false)
  const [renderError, setRenderError] = useState(null)
  const [onlineEditorLink, setOnlineEditorLink] = useState(null) // Online editor linki
  // io_net backend için ayarlar
  const [temperature, setTemperature] = useState(0.7)
  const [apiProvider, setApiProvider] = useState('io_net') // 'io_net' veya 'improved'
  const [improvements, setImprovements] = useState(null) // Opsiyonel - sadece improved backend'de var

  const handleImageUpload = (e) => {
    const file = e.target.files[0]
    if (file) {
      const reader = new FileReader()
      reader.onloadend = () => {
        setImagePreview(reader.result)
        setImage(reader.result)
      }
      reader.readAsDataURL(file)
    }
  }

  const generateCode = async () => {
    if (!image && !description.trim()) {
      setError('Lütfen görsel yükleyin veya metin açıklaması girin!')
      return
    }

    setLoading(true)
    setError(null)
    setCode('')
    setRenderedImage(null)
    setImprovements(null)
    setRenderError(null)

    try {
      // io_net backend için payload
      const payload = {
        image: image,
        description: description,
        instruction: instruction,
        temperature: temperature
      }
      
      // Improved backend için ek parametreler (opsiyonel)
      if (apiProvider === 'improved') {
        // Bu parametreler sadece improved backend'de çalışır
        // payload.thinking_mode = thinkingMode
        // payload.enable_self_correction = enableSelfCorrection
        // payload.enable_few_shot = enableFewShot
      }
      
      const response = await axios.post(`${API_BASE}/generate`, payload)

      if (response.data.success) {
        setCode(response.data.code)
        
        // API provider'ı response'dan al
        if (response.data.api_provider) {
          setApiProvider(response.data.api_provider)
        }
        
        // Improvement bilgilerini kaydet (sadece improved backend'de var)
        if (response.data.improvements) {
          setImprovements(response.data.improvements)
        }
        
        // Otomatik render et
        setTimeout(() => renderCode(response.data.code), 500)
      } else {
        setError(response.data.error || 'Kod üretilemedi')
      }
    } catch (err) {
      console.error('Generate error:', err)
      console.error('Error response:', err.response?.data)
      
      const errorData = err.response?.data || {}
      let errorMsg = errorData.error || errorData.details || err.message || 'Bir hata oluştu'
      
      // Rate limit hatası için özel mesaj
      if (err.response?.status === 429 || errorData.type === 'rate_limit') {
        errorMsg = `⏳ Rate Limit: ${errorMsg}\n\n💡 ${errorData.suggestion || 'Lütfen birkaç saniye bekleyip tekrar deneyin.'}`
        setTimeout(() => {
          if (confirm('10 saniye geçti. Tekrar denemek ister misiniz?')) {
            generateCode()
          }
        }, 10000)
      }
      
      setError(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  const renderCode = async (codeToRender = null) => {
    const codeToUse = codeToRender || code
    if (!codeToUse) {
      setError('Render edilecek kod yok!')
      return
    }

    setLoading(true)
    setError(null)
    setRenderError(null)

    try {
      const response = await axios.post(`${API_BASE}/render`, {
        code: codeToUse
      })

      // Online editor linki varsa kaydet (başarılı olsa bile)
      if (response.data.online_editor_link) {
        setOnlineEditorLink(response.data.online_editor_link)
        console.log('🌐 Online editor linki alındı:', response.data.online_editor_link)
      } else {
        setOnlineEditorLink(null)
      }
      
      if (response.data.success) {
        const imageData = response.data.image
        if (imageData) {
          // Base64 string'i kontrol et
          const base64Image = imageData.startsWith('data:') 
            ? imageData 
            : `data:image/png;base64,${imageData}`
          
          console.log('✅ Render başarılı, görsel set ediliyor...')
          console.log('Image data length:', imageData.length)
          console.log('Method:', response.data.method)
          
          setRenderedImage(base64Image)
          setRenderError(null)
          
          if (response.data.method === 'online') {
            console.log('✅ Online render ile başarılı (Selenium)')
          }
        } else {
          console.error('⚠️ Response başarılı ama image data yok!')
          setRenderError('Render başarılı ama görsel verisi alınamadı')
        }
      } else {
        if (response.data.error) {
          setRenderError(response.data.error)
          setError(`Render hatası: ${response.data.error}`)
        }
      }
    } catch (err) {
      const errorMsg = err.response?.data?.error || err.response?.data?.details || err.message || 'Render hatası'
      console.error('Render error:', err.response?.data || err)
      setError(errorMsg)
      setRenderError(errorMsg)
      // Online editor linki varsa kaydet
      if (err.response?.data?.online_editor_link) {
        setOnlineEditorLink(err.response.data.online_editor_link)
      } else {
        setOnlineEditorLink(null)
      }
    } finally {
      setLoading(false)
    }
  }

  // KALDIRILDI: autoFixCode - Artık backend'de otomatik çalışıyor
  // Self-correction loop backend'de otomatik olarak çalışıyor

  const fixCodeWithImages = async () => {
    if (!code || !renderError) {
      setError('Düzeltme için kod ve hata mesajı gereklidir!')
      return
    }

    if (!image) {
      setError('Düzeltme için orijinal görsel gereklidir!')
      return
    }

    setLoading(true)
    setError(null)

    try {
      let originalBase64 = image
      if (image.startsWith('data:image')) {
        originalBase64 = image.split(',')[1]
      }

      let renderedBase64 = renderedImage
      if (renderedImage && renderedImage.startsWith('data:image')) {
        renderedBase64 = renderedImage.split(',')[1]
      }

      const response = await axios.post(`${API_BASE}/fix-with-images`, {
        code: code,
        error: renderError,
        original_image: originalBase64,
        rendered_image: renderedBase64 || null,
        thinking_mode: thinkingMode
      })

      if (response.data.success) {
        setCode(response.data.code)
        setRenderError(null)
        setTimeout(() => renderCode(response.data.code), 500)
      } else {
        setError(`Düzeltme başarısız: ${response.data.error}`)
      }
    } catch (err) {
      console.error('Fix with images error:', err)
      const errorData = err.response?.data || {}
      const errorMsg = errorData.error || errorData.details || err.message || 'Düzeltme hatası'
      setError(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  const copyCode = () => {
    navigator.clipboard.writeText(code)
    alert('Kod panoya kopyalandı! ✅')
  }

  const improveCode = async () => {
    if (!image || !renderedImage) {
      setError('İyileştirme için hem orijinal görsel hem de render edilmiş görsel gereklidir!')
      return
    }

    if (!code) {
      setError('İyileştirilecek kod yok!')
      return
    }

    setImproving(true)
    setError(null)

    try {
      let renderedBase64 = renderedImage
      if (renderedImage.startsWith('data:image')) {
        renderedBase64 = renderedImage.split(',')[1]
      }

      let originalBase64 = image
      if (image.startsWith('data:image')) {
        originalBase64 = image.split(',')[1]
      }

      const response = await axios.post(`${API_BASE}/improve`, {
        code: code,
        original_image: originalBase64,
        rendered_image: renderedBase64,
        thinking_mode: thinkingMode
      })

      if (response.data.success) {
        setCode(response.data.code)
        setTimeout(() => renderCode(response.data.code), 500)
      } else {
        setError(response.data.error || 'Kod iyileştirilemedi')
      }
    } catch (err) {
      console.error('Improve error:', err)
      const errorData = err.response?.data || {}
      const errorMsg = errorData.error || errorData.details || err.message || 'İyileştirme hatası'
      setError(errorMsg)
    } finally {
      setImproving(false)
    }
  }

  return (
    <div className="app">
      <div className="container">
        <header>
          <h1>🎨 3D Obje → OpenSCAD Kodu Üretici</h1>
          <p>Görsel veya açıklamadan OpenSCAD kodu üretin (io_net Backend)</p>
        </header>

        <div className="main-content">
          {/* Sol Panel - Input */}
          <div className="input-panel">
            <div className="card">
              <h2>📷 Görsel Yükle</h2>
              <div className="image-upload">
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleImageUpload}
                  id="image-upload"
                  style={{ display: 'none' }}
                />
                <label htmlFor="image-upload" className="upload-button">
                  {imagePreview ? '🖼️ Görsel Değiştir' : '📷 Görsel Seç'}
                </label>
                {imagePreview && (
                  <div className="image-preview">
                    <img src={imagePreview} alt="Preview" />
                  </div>
                )}
              </div>
            </div>

            <div className="card">
              <h2>📝 Metin Açıklaması</h2>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="3D objenin detaylı açıklamasını yazın..."
                rows={5}
              />
            </div>

            <div className="card">
              <h2>⚙️ Ek Talimat (Opsiyonel)</h2>
              <input
                type="text"
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder="Özel istekleriniz..."
              />
            </div>

            {/* io_net Backend Ayarları */}
            <div className="card" style={{ padding: '15px', backgroundColor: '#fff3e0', border: '2px solid #FF9800' }}>
              <h3 style={{ marginTop: 0, color: '#E65100' }}>⚙️ io_net Backend Ayarları</h3>
              
              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px', fontWeight: '500' }}>
                  🌡️ Temperature: {temperature.toFixed(1)}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  style={{ width: '100%', cursor: 'pointer' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#666', marginTop: '4px' }}>
                  <span>0.0 (Deterministik)</span>
                  <span>0.5</span>
                  <span>1.0 (Yaratıcı)</span>
                </div>
                <small style={{ display: 'block', marginTop: '8px', color: '#666', fontSize: '12px' }}>
                  Düşük değerler daha tutarlı, yüksek değerler daha yaratıcı sonuçlar üretir
                </small>
              </div>
            </div>

            <button
              className="generate-button"
              onClick={generateCode}
              disabled={loading}
            >
              {loading ? '⏳ İşleniyor...' : '⚙️ OpenSCAD Kodu Üret'}
            </button>
          </div>

          {/* Sağ Panel - Output */}
          <div className="output-panel">
            {error && (
              <div className="error-message">
                <strong>❌ Hata:</strong><br />
                {error}
                <br /><br />
                <small>💡 Backend terminal'inde detaylı hata mesajını kontrol edin.</small>
              </div>
            )}

            {/* Improvement Metrikleri (Sadece Improved Backend'de var) */}
            {apiProvider === 'improved' && improvements && (
              <div className="card" style={{ 
                padding: '15px', 
                backgroundColor: '#e8f5e9', 
                border: '2px solid #4CAF50',
                marginBottom: '20px'
              }}>
                <h3 style={{ marginTop: 0, color: '#2e7d32' }}>📊 İyileştirme Metrikleri</h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '13px' }}>
                  <div>
                    <strong>Syntax Hataları:</strong> {improvements.syntax_errors_found || 0}
                  </div>
                  <div>
                    <strong>Düzeltildi:</strong> {improvements.syntax_errors_fixed ? '✅ Evet' : '❌ Hayır'}
                  </div>
                  <div>
                    <strong>Self-Correction:</strong> {improvements.self_correction_iterations || 0} iterasyon
                  </div>
                  <div>
                    <strong>Few-Shot:</strong> {improvements.few_shot_examples_used ? '✅ Kullanıldı' : '❌ Kullanılmadı'}
                  </div>
                </div>
              </div>
            )}
            
            {/* io_net Backend Bilgisi */}
            {apiProvider === 'io_net' && code && (
              <div className="card" style={{ 
                padding: '15px', 
                backgroundColor: '#fff3e0', 
                border: '2px solid #FF9800',
                marginBottom: '20px'
              }}>
                <h3 style={{ marginTop: 0, color: '#E65100' }}>🔗 API Provider: io_net</h3>
                <div style={{ fontSize: '13px' }}>
                  <div><strong>Model:</strong> Qwen/Qwen2.5-VL-32B-Instruct</div>
                  <div><strong>Temperature:</strong> {temperature.toFixed(1)}</div>
                </div>
              </div>
            )}

            <div className="card">
              <div className="card-header">
                <h2>📄 OpenSCAD Kodu</h2>
                {code && (
                  <button className="icon-button" onClick={copyCode} title="Kopyala">
                    📋
                  </button>
                )}
              </div>
              <textarea
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Üretilen kod burada görünecek..."
                rows={15}
                readOnly={!code}
                className="code-textarea"
              />
            </div>

            <div className="card">
              <div className="card-header">
                <h2>🖼️ Render Önizleme</h2>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {/* io_net backend'de improve ve fix endpoint'leri yok, bu yüzden butonları gizle */}
                  {apiProvider === 'improved' && code && renderedImage && image && (
                    <button
                      className="icon-button"
                      onClick={improveCode}
                      disabled={loading || improving}
                      title="Görselle Karşılaştırarak Geliştir (Sadece Improved Backend)"
                      style={{ backgroundColor: '#4CAF50', color: 'white' }}
                    >
                      {improving ? '⏳' : '✨'}
                    </button>
                  )}
                  {apiProvider === 'improved' && code && renderError && image && (
                    <button
                      className="icon-button"
                      onClick={fixCodeWithImages}
                      disabled={loading}
                      title="Hatayı, Görselleri ve Kodu Analiz Ederek Düzelt (Sadece Improved Backend)"
                      style={{ backgroundColor: '#FF9800', color: 'white' }}
                    >
                      🔧
                    </button>
                  )}
                  {code && (
                    <button
                      className="icon-button"
                      onClick={() => renderCode()}
                      disabled={loading || improving}
                      title="Render Et"
                    >
                      🔄
                    </button>
                  )}
                </div>
              </div>
              <div className="render-preview">
                {renderedImage ? (
                  <img src={renderedImage} alt="Rendered" />
                ) : (
                  <div className="render-placeholder">
                    {code ? 'Render edilmedi' : 'Kod üretin veya render edin'}
                  </div>
                )}
              </div>
              {/* Online editor linki - her zaman göster (render başarılı olsa bile) */}
              {onlineEditorLink && (
                <div style={{ 
                  marginTop: '10px', 
                  padding: '12px', 
                  backgroundColor: '#e3f2fd', 
                  border: '1px solid #2196F3',
                  borderRadius: '4px',
                  fontSize: '12px'
                }}>
                  <strong>🌐 Online Editor'de Aç:</strong><br />
                  <a 
                    href={onlineEditorLink} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    style={{ 
                      color: '#1976d2', 
                      textDecoration: 'underline',
                      fontSize: '13px',
                      wordBreak: 'break-all',
                      display: 'inline-block',
                      marginTop: '5px'
                    }}
                  >
                    {onlineEditorLink}
                  </a>
                  <br />
                  <small style={{ display: 'block', marginTop: '8px', color: '#666' }}>
                    💡 Kodunuz otomatik olarak online editor'de açılacak. Orada render'ı görebilirsiniz.
                  </small>
                </div>
              )}
              {renderError && (
                <div style={{ 
                  marginTop: '10px', 
                  padding: '10px', 
                  backgroundColor: '#ffebee', 
                  border: '1px solid #f44336',
                  borderRadius: '4px',
                  fontSize: '12px'
                }}>
                  <strong>❌ Render Hatası:</strong><br />
                  {renderError}
                  {renderError && renderError.includes('Selenium') && (
                    <div style={{ marginTop: '10px', padding: '8px', backgroundColor: '#fff3cd', borderRadius: '4px' }}>
                      <strong>💡 Not:</strong> Online render için Selenium kurulumu gerekli. 
                      Backend terminalinde <code>pip install selenium webdriver-manager</code> komutunu çalıştırın.
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
