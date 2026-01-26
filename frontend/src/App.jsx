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
  const [thinkingMode, setThinkingMode] = useState(false)
  
  // YENİ: Improved backend özellikleri
  const [enableSelfCorrection, setEnableSelfCorrection] = useState(true)
  const [enableFewShot, setEnableFewShot] = useState(true)
  const [improvements, setImprovements] = useState(null)

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
      const response = await axios.post(`${API_BASE}/generate`, {
        image: image,
        description: description,
        instruction: instruction,
        thinking_mode: thinkingMode,
        // YENİ: Improved backend parametreleri
        enable_self_correction: enableSelfCorrection,
        enable_few_shot: enableFewShot
      })

      if (response.data.success) {
        setCode(response.data.code)
        
        // YENİ: Improvement bilgilerini kaydet
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

      if (response.data.success) {
        setRenderedImage(`data:image/png;base64,${response.data.image}`)
        setRenderError(null)
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
          <p>Görsel veya açıklamadan OpenSCAD kodu üretin (Improved Backend v2.0)</p>
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

            {/* YENİ: Improved Backend Ayarları */}
            <div className="card" style={{ padding: '15px', backgroundColor: '#f0f7ff', border: '2px solid #2196F3' }}>
              <h3 style={{ marginTop: 0, color: '#1976D2' }}>✨ Improved Backend Özellikleri</h3>
              
              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={enableSelfCorrection}
                    onChange={(e) => setEnableSelfCorrection(e.target.checked)}
                    style={{ width: '20px', height: '20px', cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: '14px', fontWeight: '500' }}>
                    🔄 Self-Correction Loop {enableSelfCorrection ? '(Açık)' : '(Kapalı)'}
                  </span>
                </label>
                <small style={{ display: 'block', marginLeft: '30px', color: '#666', fontSize: '12px' }}>
                  Model kendi kodunu gözden geçirip otomatik düzeltir (Syntax hatalarını azaltır)
                </small>
              </div>

              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={enableFewShot}
                    onChange={(e) => setEnableFewShot(e.target.checked)}
                    style={{ width: '20px', height: '20px', cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: '14px', fontWeight: '500' }}>
                    📚 Few-Shot Learning {enableFewShot ? '(Açık)' : '(Kapalı)'}
                  </span>
                </label>
                <small style={{ display: 'block', marginLeft: '30px', color: '#666', fontSize: '12px' }}>
                  Başarılı örneklerle model eğitilir (Daha tutarlı kod formatı)
                </small>
              </div>

              <div>
                <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={thinkingMode}
                    onChange={(e) => setThinkingMode(e.target.checked)}
                    style={{ width: '20px', height: '20px', cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: '14px', fontWeight: '500' }}>
                    🧠 Thinking Mode {thinkingMode ? '(Açık)' : '(Kapalı)'}
                  </span>
                </label>
                <small style={{ display: 'block', marginLeft: '30px', color: '#666', fontSize: '12px' }}>
                  {thinkingMode 
                    ? 'Model önce düşünür, sonra cevap verir. Daha detaylı analiz için.' 
                    : 'Model doğrudan cevap verir. Daha hızlı sonuçlar için.'}
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

            {/* YENİ: Improvement Metrikleri */}
            {improvements && (
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
                  {code && renderedImage && image && (
                    <button
                      className="icon-button"
                      onClick={improveCode}
                      disabled={loading || improving}
                      title="Görselle Karşılaştırarak Geliştir"
                      style={{ backgroundColor: '#4CAF50', color: 'white' }}
                    >
                      {improving ? '⏳' : '✨'}
                    </button>
                  )}
                  {code && renderError && image && (
                    <button
                      className="icon-button"
                      onClick={fixCodeWithImages}
                      disabled={loading}
                      title="Hatayı, Görselleri ve Kodu Analiz Ederek Düzelt"
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
